import os, hmac, json, time, base64
import hashlib
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

from .drivers import registry as drv
from .hysteresis import Hysteresis

UDM_DIR = Path(__file__).resolve().parent.parent / ".udm"
UDM_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_DIR = UDM_DIR / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
LAST = UDM_DIR / "last_receipt.json"

def _active_secret() -> bytes:
    hexkey = os.getenv("UDM_ACTIVE_SECRET", "0"*64)
    try:
        return bytes.fromhex(hexkey)
    except Exception:
        return b"\x00"*32

def _sign(body: Dict[str, Any]) -> Dict[str, Any]:
    """HMAC-SHA256 over canonical JSON bytes (utf-8). Lowercase hex signature."""
    canonical = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_active_secret(), canonical, hashlib.sha256).hexdigest()
    return {
        "receipt_body": body,
        "signature": sig,
        "signed": int(time.time()),
    }

def _save_receipt(rec: Dict[str, Any]):
    ts = rec.get("signed") or int(time.time())
    path = RECEIPTS_DIR / f"receipt_{ts}.json"
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    LAST.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return str(path)

def _hash_12(rec: Dict[str, Any]) -> str:
    raw = json.dumps(rec, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]

def compute_scp(signals: Dict[str, Any]) -> Tuple[float, float, float, str]:
    S, C, P = drv.compute(signals)
    return S, C, P, drv.active_id()

def compute_scp_shadow(signals: Dict[str, Any], shadow_id: str) -> Optional[Dict[str, Any]]:
    try:
        S, C, P = drv.compute_with(signals, shadow_id)
        return {"driver_id": shadow_id, "S": S, "C": C, "P": P}
    except Exception:
        return None

def gates_plan(scope: str, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    # Very minimal planner gate (expand as needed)
    violations = []
    cons = (plan or {}).get("constraints", {})
    dl = (cons or {}).get("download", {}) or {}
    url = dl.get("url")
    if url:
        allowed = ["github.com", "raw.githubusercontent.com", "aka.ms", "microsoft.com"]
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        if not any(host.endswith(d) for d in allowed):
            violations.append(f"download_domain_not_allowed:{host}")
    # Add more: budget bounds, mask_required, etc.
    return (len(violations) == 0, violations)

class Regulator:
    def __init__(self):
        self.hys = Hysteresis()
        self.actor_ctx: Dict[str, Any] = {}

    def reset_hys(self, actor_id: str = None):
        self.hys.reset()
        if actor_id:
            self.actor_ctx.pop(actor_id, None)

    def govern(self, signals: Dict[str, Any], context: Dict[str, Any], content: Dict[str, Any] = None, policy: Dict[str, Any] = None):
        S, C, P, driver_id = compute_scp(signals or {})
        hys = self.hys.update(S, C, P)
        mode = hys["mode"]

        shadow_id = os.getenv("UDM_DRIVER_SHADOW")
        shadow = None
        if shadow_id and shadow_id != driver_id:
            shadow = compute_scp_shadow(signals or {}, shadow_id)

        reasons: Dict[str, Any] = {
            "driver_id": driver_id,
            "S": S, "C": C, "P": P,
            "hysteresis": {
                "m": self.hys.m,
                "calm_windows": self.hys.calm_windows
            },
        }
        if shadow is not None:
            reasons["shadow"] = shadow

        body = {
            "state": mode,
            "reasons": reasons,
            "context": context or {},
            "content": content or {},
            "policy": policy or {},
            "ts": int(time.time()),
            "api_version": os.getenv("UDM_API_VERSION", "1.0.0")
        }
        rec = _sign(body)
        path = _save_receipt(rec)
        return mode, rec, path

    def replay(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        # Basic signature verification
        body = receipt.get("receipt_body") or {}
        sig = receipt.get("signature") or ""
        canonical = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        expect = hmac.new(_active_secret(), canonical, hashlib.sha256).hexdigest()
        return {
            "valid": (expect == sig),
            "expected": expect,
            "provided": sig,
            "hash_12": _hash_12(receipt),
        }

REG = Regulator()
