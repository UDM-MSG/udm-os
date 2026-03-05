from fastapi import FastAPI, APIRouter, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional
from pathlib import Path
import os, json, time

from .regulator import REG, gates_plan, _hash_12, LAST, UDM_DIR
from .config_layer import get as cfg_get, load as cfg_load, get_path as cfg_path
from .logs import log_event, tail as log_tail
from .usc import actuate as usc_actuate
from .drivers import registry as drv
from .sim_domain import SIMS

app = FastAPI(title="UDM OS Kernel", version=os.getenv("UDM_API_VERSION", "1.0.0"))


def _admin_token_ok(sent: Any) -> bool:
    """True if no admin token configured, or sent token matches (after strip)."""
    admin = (os.getenv("UDM_ADMIN_TOKEN") or "").strip()
    if not admin:
        return True
    if sent is None:
        return False
    return (str(sent).strip() == admin)


class DomainSimReq(BaseModel):
    iters: int = 50
    mode: str = "random"
    seed: Optional[int] = None


# Domain sim router (registered first so /simulate/* is always available)
sim_router = APIRouter(prefix="/simulate", tags=["simulate"])

@sim_router.get("/list")
def simulate_list():
    return {k: {"modes": v["modes"]} for k, v in SIMS.items()}

def _run_domain_sim(domain: str, params: Dict[str, Any]):
    spec = SIMS.get(domain)
    if not spec:
        return {"ok": False, "error": "domain_not_found"}, 404
    iters = int((params or {}).get("iters", 50))
    mode = (params or {}).get("mode", "random")
    seed = (params or {}).get("seed")
    if mode not in spec["modes"]:
        mode = "random"
    seq = spec["fn"](iters=iters, mode=mode, seed=seed)
    counts = {"CLOSED": 0, "WATCH": 0, "OPEN": 0}
    samples = []
    for i, s in enumerate(seq):
        ctx = {"scope": f"sim.{domain}", "actor_id": f"sim-{domain}"}
        mode_state, rec, _ = REG.govern(s, ctx, {}, {})
        counts[mode_state] = counts.get(mode_state, 0) + 1
        reasons = rec.get("receipt_body", {}).get("reasons", {})
        if len(samples) < 8:
            samples.append({
                "S": reasons.get("S"),
                "C": reasons.get("C"),
                "P": reasons.get("P"),
                "state": mode_state,
            })
    return ({
        "ok": True,
        "domain": domain,
        "iters": iters,
        "mode": mode,
        "seed": seed,
        "summary": counts,
        "samples": samples,
    }, 200)

@sim_router.post("/ai")
def simulate_ai(req: DomainSimReq):
    res, code = _run_domain_sim("ai", req.model_dump())
    return Response(content=json.dumps(res), status_code=code, media_type="application/json")

@sim_router.post("/weather")
def simulate_weather(req: DomainSimReq):
    res, code = _run_domain_sim("weather", req.model_dump())
    return Response(content=json.dumps(res), status_code=code, media_type="application/json")

@sim_router.post("/traffic")
def simulate_traffic(req: DomainSimReq):
    res, code = _run_domain_sim("traffic", req.model_dump())
    return Response(content=json.dumps(res), status_code=code, media_type="application/json")

app.include_router(sim_router)

# CORS (open for local dev; restrict in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root and dashboard (so GET / and GET /dashboard work)
_kernel_root = Path(__file__).resolve().parent.parent
dash = _kernel_root / "dashboard"
pub = _kernel_root / "public_dashboard"


@app.get("/")
def root_redirect():
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    idx = dash / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text(encoding="utf-8", errors="replace"))
    return HTMLResponse("<p>UDM OS Kernel. Dashboard not found. Try <a href='/public/'>/public/</a> or <a href='/health'>/health</a>.</p>", status_code=404)


# Public API routes (must be registered before /public mount so they take precedence)
@app.get("/public/health")
def public_health():
    return {"ok": True}

@app.get("/public/state")
def public_state():
    if LAST.exists():
        rec = json.loads(LAST.read_text(encoding="utf-8"))
        body = rec.get("receipt_body", {})
        return {"ok": True, "available": True, "state": body.get("state"), "last_receipt_hash": _hash_12(rec)}
    return {"ok": True, "available": False, "state": "CLOSED", "last_receipt_hash": None}

# Static dashboards if present
if dash.exists():
    app.mount("/dashboard_static", StaticFiles(directory=str(dash)), name="dashboard_static")
if pub.exists():
    app.mount("/public", StaticFiles(directory=str(pub)), name="public")

# -------- Models
class GovernReq(BaseModel):
    signals: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    content: Dict[str, Any] = {}
    policy: Dict[str, Any] = {}

class PlanReq(BaseModel):
    scope: str
    plan: Dict[str, Any]


class ActuateReq(BaseModel):
    receipt: Dict[str, Any]
    action: Dict[str, Any]  # {type, params, action_id, ttl_s}


class LearnReq(BaseModel):
    admin_token: Optional[str] = None
    batch_stats: Dict[str, Any] = {}
    driver_id: str = "emergent"


# -------- Health / Meta / Public
@app.get("/health")
def health():
    hys_depth = REG.hys.m
    version = os.getenv("UDM_API_VERSION", "1.0.0")
    usc_required = os.getenv("USC_REQUIRED", "0")
    return {"ok": True, "version": version, "hys_depth": hys_depth, "usc_required": usc_required, "domain_sims": True}

@app.get("/meta/version")
def meta_version():
    return {"api_version": os.getenv("UDM_API_VERSION", "1.0.0")}

@app.get("/timeline")
def timeline():
    # Minimal placeholder (extend as needed)
    return [{"ts": int(time.time()), "event": "kernel_alive"}]

# -------- Admin
@app.post("/admin/hys/reset")
def admin_hys_reset(body: Dict[str, Any] = Body(default={})):
    actor_id = (body or {}).get("actor_id")
    REG.reset_hys(actor_id=actor_id)
    return {"ok": True, "actor_id": actor_id}


@app.post("/admin/hys/update_thresholds")
def admin_hys_update_thresholds(body: Dict[str, Any] = Body(default={})):
    """Get or set enter-OPEN (s_open, c_open, p_open) and fault-close (s_min, c_min, p_max). Admin-token gated."""
    if not _admin_token_ok((body or {}).get("admin_token")):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    h = REG.hys
    # Optional updates (only if provided)
    for key, default in (
        ("s_open", 0.72), ("c_open", 0.77), ("p_open", 0.28),
        ("s_min", 0.70), ("c_min", 0.75), ("p_max", 0.30),
    ):
        v = (body or {}).get(key)
        if v is not None:
            setattr(h, key, max(0.0, min(1.0, float(v))))
    current = {
        "s_open": h.s_open, "c_open": h.c_open, "p_open": h.p_open,
        "s_min": h.s_min, "c_min": h.c_min, "p_max": h.p_max,
    }
    return {"ok": True, "current": current}


@app.post("/admin/ai_risky/update")
def admin_ai_risky_update(body: Dict[str, Any] = Body(default={})):
    """Update AI risky severity knobs (env vars for domain sim / hard test tuning). Admin-token gated."""
    if not _admin_token_ok((body or {}).get("admin_token")):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    knobs = (
        "AIG_RISKY_MIN_ERR",
        "AIG_RISKY_MAX_ERR",
        "AIG_RISKY_MIN_VIOL",
        "AIG_RISKY_MAX_VIOL",
        "AIG_RISKY_MAX_AGR",
        "AIG_RISKY_LAT_MIN",
        "AIG_RISKY_LAT_MAX",
    )
    updated = {}
    for key in knobs:
        val = (body or {}).get(key)
        if val is not None and str(val).strip() != "":
            os.environ[key] = str(val).strip()
            updated[key] = os.environ[key]
    return {"ok": True, "updated": updated}


# -------- Gates / Plan
@app.post("/gates/plan")
def gates_plan_check(req: PlanReq):
    passed, violations = gates_plan(req.scope, req.plan)
    return {"pass": passed, "violations": violations}

# -------- Govern (versioned)
api_v1 = APIRouter(prefix="/govern/v1", tags=["govern"])

@api_v1.post("")
def govern_v1(req: GovernReq):
    mode, receipt, path = REG.govern(req.signals, req.context, req.content, req.policy)
    reasons = receipt.get("receipt_body", {}).get("reasons", {})
    return {"state": mode, "reason_codes": reasons, "receipt": receipt}

# Keep backward-compatible alias (unversioned)
@app.post("/govern")
def govern_alias(req: GovernReq):
    return govern_v1(req)

app.include_router(api_v1)

# -------- Replay
@app.post("/replay")
def replay(body: Dict[str, Any]):
    rec = body.get("receipt") or body
    return REG.replay(rec)

@app.post("/ui/run_dsl")
def ui_run_dsl(body: Dict[str, Any] = Body(default={})):
    """Minimal stub: run DSL line through govern. Full DSL parsing is in kernel_app.py.bak.refactor."""
    line = (body or {}).get("line", "").strip()
    if not line:
        return Response(
            content=json.dumps({"ok": False, "detail": "missing line"}),
            status_code=400,
            media_type="application/json",
        )
    # Minimal interpret: treat as S/C/P-ish and call govern
    try:
        signals = {"s": 0.7, "c": 0.75, "p": 0.25}
        if "234" in line or "1 " in line:
            signals = {"s": 0.85, "c": 0.85, "p": 0.15}
        mode, receipt, _ = REG.govern(
            signals,
            {"scope": "planner.safe", "actor_id": "user"},
            {"input_type": "text", "text": line[:200]},
            {},
        )
        reasons = receipt.get("receipt_body", {}).get("reasons", {})
        return {
            "ok": True,
            "kernel": {"state": mode, "reason_codes": reasons, "receipt": receipt},
        }
    except Exception as e:
        return Response(
            content=json.dumps({"ok": False, "detail": str(e)}),
            status_code=500,
            media_type="application/json",
        )


@app.post("/ui/replay_last")
def replay_last():
    if LAST.exists():
        rec = json.loads(LAST.read_text(encoding="utf-8"))
        result = REG.replay(rec)
        return {"ok": result.get("valid"), "replay": {"match": result.get("valid"), "hash_12": result.get("hash_12")}}
    return {"ok": False, "replay": {}}

# -------- Safety Conduit: Actuation (USC)
@app.post("/actuate")
def actuate_endpoint(req: ActuateReq):
    code, result = usc_actuate({"receipt": req.receipt, "action": req.action})
    return Response(content=json.dumps(result), status_code=code, media_type="application/json")


# -------- Simulator (generic)
@app.post("/simulate/govern")
def simulate(body: Dict[str, Any] = Body(default={})):
    """
    body: { "iters": 50, "signals": [{...}, {...}], "noise": 0.0 }
    - if signals is a single dict, reuse it each iter
    - if a list, iterate through (wrap if needed)
    """
    iters = int(body.get("iters", 30))
    sigs = body.get("signals", {}) or {}
    if isinstance(sigs, dict):
        seq = [sigs] * iters
    elif isinstance(sigs, list) and sigs:
        seq = [sigs[i % len(sigs)] for i in range(iters)]
    else:
        seq = [{}] * iters

    modes = {"CLOSED": 0, "WATCH": 0, "OPEN": 0}
    recs = []
    for s in seq:
        mode, rec, _ = REG.govern(s, {"scope": "simulate", "actor_id": "sim"}, {}, {})
        modes[mode] = modes.get(mode, 0) + 1
        recs.append(rec.get("receipt_body", {}).get("reasons", {}))
    return {"summary": modes, "iters": iters, "samples": min(5, len(recs)), "reasons_samples": recs[:5]}


# -------- Drivers: Emergent learn (manual, token-gated)
@app.post("/drivers/emergent/learn")
def drivers_emergent_learn(req: LearnReq):
    if os.getenv("UDM_DRIVER_LEARN_ENABLED", "0") != "1":
        return Response(
            content=json.dumps({"ok": False, "error": "learn_disabled"}),
            status_code=403,
            media_type="application/json",
        )
    if not _admin_token_ok(req.admin_token):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    d = drv.get(req.driver_id)
    if not d or not hasattr(d, "update_from_batch"):
        return Response(
            content=json.dumps({"ok": False, "error": "driver_not_found_or_no_learning"}),
            status_code=400,
            media_type="application/json",
        )
    try:
        res = d.update_from_batch(req.batch_stats or {})
        code = 200 if (isinstance(res, dict) and res.get("ok", False)) else 400
        return Response(content=json.dumps(res), status_code=code, media_type="application/json")
    except Exception as e:
        return Response(
            content=json.dumps({"ok": False, "error": "learn_internal_error", "detail": str(e)}),
            status_code=500,
            media_type="application/json",
        )


@app.post("/drivers/emergent/autotune")
def drivers_emergent_autotune(body: Dict[str, Any] = Body(default={})):
    """Run several learn steps with synthetic risky-like batch_stats and conservative target to reduce risky OPEN. Admin-token gated."""
    if not _admin_token_ok((body or {}).get("admin_token")):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    if os.getenv("UDM_DRIVER_LEARN_ENABLED", "0") != "1":
        return Response(
            content=json.dumps({"ok": False, "error": "learn_disabled"}),
            status_code=403,
            media_type="application/json",
        )
    d = drv.get("emergent")
    if not d or not hasattr(d, "update_from_batch"):
        return Response(
            content=json.dumps({"ok": False, "error": "driver_not_found_or_no_learning"}),
            status_code=400,
            media_type="application/json",
        )
    steps = int((body or {}).get("steps", 4))
    seed = (body or {}).get("seed")
    import random
    rng = random.Random(seed)
    done = 0
    for i in range(steps):
        # Synthetic risky-like stats with conservative target so driver learns to map them stricter
        batch_stats = {
            "agreement_score": 0.35 + 0.25 * rng.random(),
            "schema_violation_rate": 0.40 + 0.30 * rng.random(),
            "error_rate": 0.30 + 0.25 * rng.random(),
            "ok_rate": 0.55 + 0.25 * rng.random(),
            "latency_var": 0.45 + 0.25 * rng.random(),
            "queue_growth": 0.1 * rng.random(),
            "target": {"S": 0.85, "C": 0.85, "P": 0.15},
        }
        try:
            res = d.update_from_batch(batch_stats)
            if isinstance(res, dict) and res.get("ok"):
                done += 1
        except Exception:
            pass
    return Response(
        content=json.dumps({"ok": True, "steps_run": done, "steps_requested": steps}),
        status_code=200,
        media_type="application/json",
    )


# -------- Tests: AI Governance Hard Test (admin-token gated)
@app.post("/tests/ai_gov/run")
def tests_ai_gov_run(body: Dict[str, Any] = Body(default={})):
    """
    POST body can override env for this run:
    { "admin_token": "...", "AIG_SCENARIOS": 180, "AIG_RISKY_SHARE": 0.6, ... }
    """
    if not _admin_token_ok((body or {}).get("admin_token")):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    run_env = os.environ.copy()
    for key in ("AIG_SCENARIOS", "AIG_RISKY_SHARE", "AIG_MAX_RISKY_OPEN", "AIG_MIN_SAFE_OPEN", "AIG_SEED"):
        if key in (body or {}):
            run_env[key] = str((body or {})[key])

    import subprocess
    import sys

    repo_root = _kernel_root.parent  # kernel root is UDM_OS; repo root is parent
    port = os.getenv("UDM_PORT", "8000")
    cmd = [sys.executable, "tests/udm_ai_gov_hardtest.py", "--host", f"http://localhost:{port}"]
    try:
        p = subprocess.run(cmd, env=run_env, capture_output=True, text=True, timeout=1200, cwd=str(repo_root))
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        ok = p.returncode == 0
        return Response(
            content=json.dumps({"ok": ok, "returncode": p.returncode, "output": out}),
            status_code=200,
            media_type="application/json",
        )
    except subprocess.TimeoutExpired:
        return Response(
            content=json.dumps({"ok": False, "error": "timeout"}),
            status_code=500,
            media_type="application/json",
        )


# -------- Tests: AI Governance Hard Test with block spec (admin-token gated)
@app.post("/tests/ai_gov/run_blocks")
def tests_ai_gov_run_blocks(body: Dict[str, Any] = Body(default={})):
    """
    Same as /tests/ai_gov/run but accepts AIG_BLOCK_SPEC and AIG_BLOCK_ROUNDS
    so the test runs in block mode (e.g. SAFE:3,RISKY:1) for calm-window-friendly stimulus.
    """
    if not _admin_token_ok((body or {}).get("admin_token")):
        return Response(
            content=json.dumps({"ok": False, "error": "forbidden"}),
            status_code=403,
            media_type="application/json",
        )
    run_env = os.environ.copy()
    for key in (
        "AIG_SCENARIOS", "AIG_RISKY_SHARE", "AIG_MAX_RISKY_OPEN", "AIG_MIN_SAFE_OPEN",
        "AIG_SEED", "AIG_EXPLAIN", "AIG_BLOCK_SPEC", "AIG_BLOCK_ROUNDS",
    ):
        if key in (body or {}):
            run_env[key] = str((body or {})[key])

    import subprocess
    import sys

    repo_root = _kernel_root.parent
    port = os.getenv("UDM_PORT", "8000")
    cmd = [sys.executable, "tests/udm_ai_gov_hardtest.py", "--host", f"http://localhost:{port}"]
    try:
        p = subprocess.run(cmd, env=run_env, capture_output=True, text=True, timeout=1200, cwd=str(repo_root))
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        ok = p.returncode == 0
        return Response(
            content=json.dumps({"ok": ok, "returncode": p.returncode, "output": out}),
            status_code=200,
            media_type="application/json",
        )
    except subprocess.TimeoutExpired:
        return Response(
            content=json.dumps({"ok": False, "error": "timeout"}),
            status_code=500,
            media_type="application/json",
        )


# -------- Legacy /act/download (dashboard calls this; refactored kernel uses /actuate with receipt)
@app.post("/act/download")
def act_download(body: Dict[str, Any] = Body(default={})):
    """Legacy endpoint. For gated downloads use POST /actuate with receipt and action type 'download'."""
    return Response(
        content=json.dumps({
            "ok": False,
            "detail": "Use POST /actuate with a signed receipt and action { type: 'download', params: { url, save_as, sha256 }, action_id, ttl_s }.",
        }),
        status_code=501,
        media_type="application/json",
    )


# -------- Stubs (refactored kernel: restore kernel_app.py.bak.refactor for full implementations)
@app.post("/games/doom/install")
def games_doom_install_stub(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "detail": "DOOM install not in refactored kernel. Restore UDM_OS/app/kernel_app.py.bak.refactor to re-enable."}


@app.post("/games/doom/play")
def games_doom_play_stub(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "detail": "DOOM play not in refactored kernel. Restore kernel_app.py.bak.refactor to re-enable."}


# -------- Stubs: pkg, vm, sandbox, containers (dashboard buttons; no 404)
@app.get("/pkg/winget/list")
def pkg_winget_list():
    return {"ok": False, "stdout": "", "stderr": "Not in refactored kernel. Restore backup for winget."}

@app.post("/pkg/winget/install")
def pkg_winget_install(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stdout": "", "stderr": "Not in refactored kernel. Restore backup for winget."}

@app.post("/pkg/winget/upgrade")
def pkg_winget_upgrade(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stdout": "", "stderr": "Not in refactored kernel. Restore backup for winget."}

@app.post("/vm/hyperv/start")
def vm_hyperv_start(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stderr": "Not in refactored kernel. Restore backup for Hyper-V."}

@app.post("/vm/hyperv/stop")
def vm_hyperv_stop(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stderr": "Not in refactored kernel. Restore backup for Hyper-V."}

@app.post("/vm/hyperv/checkpoint")
def vm_hyperv_checkpoint(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stderr": "Not in refactored kernel. Restore backup for Hyper-V."}

@app.get("/vm/hyperv/list")
def vm_hyperv_list():
    return {"ok": False, "vms": [], "stderr": "Not in refactored kernel. Restore backup for Hyper-V."}

@app.post("/sandbox/open")
def sandbox_open(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "detail": "Not in refactored kernel. Restore backup for Sandbox."}

@app.post("/containers/docker/run")
def containers_docker_run(body: Dict[str, Any] = Body(default={})):
    return {"ok": False, "stderr": "Not in refactored kernel. Restore backup for Docker."}

# -------- Admin: Config get/reload (token-gated)
@app.post("/admin/config/get")
def admin_config_get(body: Dict[str, Any] = Body(default={})):
    admin = os.getenv("UDM_ADMIN_TOKEN")
    if admin and (body or {}).get("admin_token") != admin:
        return Response(content=json.dumps({"ok": False, "error": "forbidden"}), status_code=403, media_type="application/json")
    return {"ok": True, "path": cfg_path(), "config": cfg_get()}

@app.post("/admin/config/reload")
def admin_config_reload(body: Dict[str, Any] = Body(default={})):
    admin = os.getenv("UDM_ADMIN_TOKEN")
    if admin and (body or {}).get("admin_token") != admin:
        return Response(content=json.dumps({"ok": False, "error": "forbidden"}), status_code=403, media_type="application/json")
    cfg_load()
    t = (cfg_get().get("thresholds") if cfg_get() else {}) or {}
    for k in ("s_min","c_min","p_max","s_open","c_open","p_open","m"):
        if k in t:
            setattr(REG.hys, k, t[k])
    return {"ok": True, "config": cfg_get()}

# -------- Logs: tail events
@app.get("/logs/events")
def logs_events(lines: int = 200):
    try:
        entries = [json.loads(x) for x in log_tail(max(1, int(lines)))]
        return {"ok": True, "lines": len(entries), "events": entries}
    except Exception as e:
        return Response(content=json.dumps({"ok": False, "error": str(e)}), status_code=500, media_type="application/json")

