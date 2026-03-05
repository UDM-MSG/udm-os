# UDM_OS/app/usc.py - UDM Safety Conduit (USC)
import os
import json
import time
import hmac
import hashlib
import pathlib
import urllib.request
from typing import Dict, Any, Tuple, Optional

from .regulator import _active_secret, _hash_12, UDM_DIR, gates_plan
from pathlib import Path
from .logs import log_event
from .config_layer import get as cfg_get

def _actor_registry():
    p = Path(__file__).resolve().parents[1] / "etc" / "udm" / "actors.json"
    if not p.exists(): return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _actor_quota(actor_id: str):
    reg = _actor_registry()
    a = (reg.get("actors") or {}).get(actor_id) or (reg.get("actors") or {}).get("default") or {}
    cfg = cfg_get() or {}
    qpm_def = ((cfg.get("usc") or {}).get("qpm_default") or 300)
    burst_def = ((cfg.get("usc") or {}).get("burst_default") or 10)
    return float(a.get("qpm", qpm_def)), float(a.get("burst", burst_def))

DELIVERED_DIR = UDM_DIR / "delivered"
DELIVERED_DIR.mkdir(parents=True, exist_ok=True)
DELIVERY_DIR = UDM_DIR / "delivery"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = UDM_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
ECHO_DIR = UDM_DIR / "echo"
ECHO_DIR.mkdir(parents=True, exist_ok=True)
RL_DIR = UDM_DIR / "ratelimit"
RL_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED = os.getenv(
    "UDM_DOWNLOAD_ALLOW_HOSTS",
    "github.com,raw.githubusercontent.com,aka.ms,microsoft.com",
)
ALLOWED_DOWNLOAD_HOSTS = [h.strip() for h in _ALLOWED.split(",") if h.strip()]


def _verify_receipt_signature(receipt: Dict[str, Any]) -> bool:
    body = receipt.get("receipt_body") or {}
    sig = receipt.get("signature") or ""
    canonical = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    expect = hmac.new(_active_secret(), canonical, hashlib.sha256).hexdigest()
    return expect == sig


def _check_state_and_context(
    receipt: Dict[str, Any], expect_actor: Optional[str]
) -> Tuple[bool, str, Dict[str, Any]]:
    body = receipt.get("receipt_body") or {}
    state = body.get("state")
    ctx = body.get("context") or {}
    actor = ctx.get("actor_id")
    scope = ctx.get("scope")
    if state != "OPEN":
        return False, "state_not_open", {"state": state}
    if expect_actor and actor and (actor != expect_actor):
        return False, "actor_mismatch", {"receipt_actor": actor, "expect_actor": expect_actor}
    return True, "ok", {"scope": scope, "actor": actor}


def _safe_id(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isalnum() or ch in ("-", "_")) or "id"


def _idempotency_path(action_id: str) -> pathlib.Path:
    return DELIVERED_DIR / f"{_safe_id(action_id)}.json"


def _idempotency_check(action_id: str) -> Optional[Dict[str, Any]]:
    p = _idempotency_path(action_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _idempotency_save(action_id: str, result: Dict[str, Any]) -> None:
    p = _idempotency_path(action_id)
    p.write_text(json.dumps(result, indent=2), encoding="utf-8")


def _rl_path(actor_id: str) -> pathlib.Path:
    return RL_DIR / f"{_safe_id(actor_id or 'anon')}.json"


def _rate_limit_ok(actor_id: str) -> Tuple[bool, float]:
    qpm, burst = _actor_quota(actor_id or "anon")
    now = time.time()
    path = _rl_path(actor_id or "anon")
    state = {"allowance": burst, "last": now}
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    allowance = float(state.get("allowance", burst))
    last = float(state.get("last", now))
    elapsed = max(0.0, now - last)
    refill = (qpm / 60.0) * elapsed
    allowance = min(burst, allowance + refill)
    if allowance < 1.0:
        path.write_text(json.dumps({"allowance": allowance, "last": now}, indent=2), encoding="utf-8")
        retry = (1.0 - allowance) / max(1e-6, (qpm / 60.0))
        return False, max(0.01, retry)
    allowance -= 1.0
    path.write_text(json.dumps({"allowance": allowance, "last": now}, indent=2), encoding="utf-8")
    return True, 0.0


def _download(params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    url = (params or {}).get("url")
    save_as = (params or {}).get("save_as", "artifact.bin")
    sha256 = (params or {}).get("sha256")
    timeout = float((params or {}).get("timeout_s", 15))
    if not url:
        return False, {"reason": "missing_url"}, None
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    if not any(host.endswith(d.strip()) for d in ALLOWED_DOWNLOAD_HOSTS):
        return False, {"reason": f"download_domain_not_allowed:{host}"}, None
    base = os.path.basename(save_as) or "artifact.bin"
    dest = DOWNLOADS_DIR / base
    start = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "UDM-OS"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except Exception as e:
        return False, {"reason": "download_failed", "detail": str(e)}, None
    if sha256:
        h = hashlib.sha256(data).hexdigest()
        if h.lower() != str(sha256).lower():
            return False, {"reason": "hash_mismatch", "expected": sha256, "actual": h}, None
    dest.write_bytes(data)
    dur = int((time.time() - start) * 1000)
    return True, {"ok": True, "bytes": len(data), "path": str(dest), "duration_ms": dur}, None


def _echo(params: Dict[str, Any], action_id: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    msg = str((params or {}).get("message", ""))
    safe = _safe_id(action_id) or "echo"
    path = ECHO_DIR / f"{safe}.txt"
    start = time.time()
    path.write_text(msg, encoding="utf-8")
    dur = int((time.time() - start) * 1000)
    return True, {"ok": True, "bytes": len(msg.encode("utf-8")), "path": str(path), "duration_ms": dur}, None


def _connector_exec(
    action: Dict[str, Any], actor_id: Optional[str]
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    atype = (action or {}).get("type")
    params = (action or {}).get("params") or {}
    aid = (action or {}).get("action_id", "echo")
    if atype == "echo":
        return _echo(params, aid)
    if atype == "download":
        return _download(params)
    return False, {"reason": "connector_not_allowed_or_implemented", "type": atype}, None


def _write_delivery_receipt(
    source_receipt: Dict[str, Any], action: Dict[str, Any], result: Dict[str, Any]
) -> Dict[str, Any]:
    ts = int(time.time())
    rid_hash = _hash_12(source_receipt)
    body = source_receipt.get("receipt_body") or {}
    ctx = body.get("context") or {}
    rec_body = {
        "action_id": action.get("action_id"),
        "ts": ts,
        "actor_id": ctx.get("actor_id"),
        "scope": ctx.get("scope"),
        "type": action.get("type"),
        "params": action.get("params"),
        "result": result,
        "source_receipt_hash12": rid_hash,
    }
    out = DELIVERY_DIR / f"delivery_{ts}_{_safe_id(action.get('action_id', 'unknown'))}.json"
    out.write_text(json.dumps(rec_body, indent=2), encoding="utf-8")
    return rec_body


def actuate(envelope: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """
    envelope: { "receipt": {...}, "action": { "type", "params", "action_id", "ttl_s" } }
    """
    try:
        receipt = (envelope or {}).get("receipt") or {}
        action = (envelope or {}).get("action") or {}
        action_id = action.get("action_id")
        ttl_s = int(action.get("ttl_s", 120))
        if not action_id:
            return 400, {"ok": False, "error": "missing_action_id"}

        if not _verify_receipt_signature(receipt):
            return 400, {"ok": False, "error": "invalid_receipt_signature"}

        signed_ts = int(receipt.get("signed", 0))
        now = int(time.time())
        if ttl_s <= 0 or now - signed_ts > ttl_s:
            return 400, {
                "ok": False,
                "error": "expired_or_invalid_ttl",
                "now": now,
                "signed": signed_ts,
                "ttl_s": ttl_s,
            }

        allow, reason, ctx = _check_state_and_context(receipt, expect_actor=None)
        if not allow:
            return 403, {"ok": False, "error": reason, "ctx": ctx}

        body = receipt.get("receipt_body") or {}
        actor_id = (body.get("context") or {}).get("actor_id") or "anon"
        scope = (body.get("context") or {}).get("scope") or "default"

        rl_ok, retry_after = _rate_limit_ok(actor_id)
        if not rl_ok:
            return 429, {"ok": False, "error": "rate_limited", "retry_after_s": round(retry_after, 3)}

        prev = _idempotency_check(action_id)
        if prev is not None:
            return 200, {"ok": True, "idempotent": True, "previous": prev}

        plan = {
            "objective": f"execute:{action.get('type')}",
            "steps": [{"do": action.get("type"), "params": action.get("params")}],
            "tools": [action.get("type")],
            "sources": [],
            "constraints": {},
        }
        if action.get("type") == "download" and action.get("params"):
            p = action["params"]
            plan["constraints"] = {"download": {"url": p.get("url"), "save_as": p.get("save_as", "artifact.bin")}}

        passed, violations = gates_plan(scope="planner.safe", plan=plan)
        if not passed:
            return 400, {"ok": False, "error": "plan_violations", "violations": violations}

        ok, result, err = _connector_exec(action, actor_id)
        if not ok:
            return 400, {"ok": False, "error": "exec_failed", "detail": result}

        drec = _write_delivery_receipt(receipt, action, result)
        _idempotency_save(action_id, drec)

        return 200, {"ok": True, "delivery_receipt": drec}
    except Exception as e:
        return 500, {"ok": False, "error": "usc_internal_error", "detail": str(e)}


