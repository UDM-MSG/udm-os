#!/usr/bin/env python
# udmctl.py - UDM-OS command-line client (minimal, no external deps)
import sys, json, argparse, os, urllib.request

HOST = os.getenv("UDM_HOST", "http://localhost:8000")
ADM  = os.getenv("UDM_ADMIN_TOKEN", "")

def http(method, path, body=None, timeout=30):
    url = HOST.rstrip("/") + path
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",",":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = r.read().decode("utf-8")
        return json.loads(t) if t else {}

def cmd_status(args):
    print(json.dumps(http("GET","/health"), indent=2))

def cmd_govern(args):
    payload = {"signals": json.loads(args.signals), "context": {"scope": args.scope, "actor_id": args.actor}}
    print(json.dumps(http("POST","/govern/v1", payload), indent=2))

def cmd_sim(args):
    payload = {"iters": args.iters, "mode": args.mode}
    print(json.dumps(http("POST", f"/simulate/{args.domain}", payload), indent=2))

def cmd_receipts_last_replay(args):
    print(json.dumps(http("POST", "/ui/replay_last", {}), indent=2))

def cmd_logs(args):
    print(json.dumps(http("GET", f"/logs/events?lines={args.lines}"), indent=2))

def cmd_config_get(args):
    body = {"admin_token": ADM}
    print(json.dumps(http("POST","/admin/config/get", body), indent=2))

def cmd_config_reload(args):
    body = {"admin_token": ADM}
    print(json.dumps(http("POST","/admin/config/reload", body), indent=2))

def cmd_thresholds(args):
    body = {"admin_token": ADM}
    for k in ("s_open","c_open","p_open"):
        v = getattr(args, k)
        if v is not None: body[k] = float(v)
    print(json.dumps(http("POST","/admin/hys/update_thresholds", body), indent=2))

def cmd_test_ai(args):
    # Check kernel is reachable first (avoid long wait then "timed out")
    try:
        http("GET", "/health", timeout=10)
    except Exception as e:
        print(json.dumps({
            "error": "kernel_not_reachable",
            "detail": str(e),
            "hint": "Start the kernel first in another terminal: cd to project root, then .\\run_kernel.ps1 or .\\launch_kernel_with_admin.ps1"
        }, indent=2), file=sys.stderr)
        sys.exit(2)
    body = {"admin_token": ADM, "AIG_SCENARIOS": args.scenarios, "AIG_SEED": args.seed, "AIG_EXPLAIN": 1}
    if getattr(args, "min_safe_open", None) is not None:
        body["AIG_MIN_SAFE_OPEN"] = args.min_safe_open
    if args.blockspec:
        body["AIG_BLOCK_SPEC"] = args.blockspec
        path = "/tests/ai_gov/run_blocks"
    else:
        path = "/tests/ai_gov/run"
    # AI gov test can take 5–15+ minutes
    print("Running AI gov test (may take 5–15 min). Waiting for kernel...", file=sys.stderr)
    print(json.dumps(http("POST", path, body, timeout=1200), indent=2))

def cmd_act_echo(args):
    g = http("POST","/govern/v1", {"signals":{"s":0.95,"c":0.95,"p":0.05}, "context":{"scope":"cli","actor_id":args.actor}})
    rec = g.get("receipt") or {}
    env = {"receipt": rec, "action": {"type":"echo","params":{"message":args.message},"action_id":f"echo-{os.getpid()}", "ttl_s":120}}
    print(json.dumps(http("POST","/actuate", env), indent=2))

def main():
    ap = argparse.ArgumentParser(prog="udmctl", description="UDM-OS command-line")
    sp = ap.add_subparsers(dest="cmd")

    s = sp.add_parser("status"); s.set_defaults(func=cmd_status)
    g = sp.add_parser("govern"); g.add_argument("--signals", required=True); g.add_argument("--scope", default="cli"); g.add_argument("--actor", default="cli"); g.set_defaults(func=cmd_govern)
    sm = sp.add_parser("simulate"); sm.add_argument("domain"); sm.add_argument("--mode", default="random"); sm.add_argument("--iters", type=int, default=50); sm.set_defaults(func=cmd_sim)
    rr = sp.add_parser("replay-last"); rr.set_defaults(func=cmd_receipts_last_replay)
    lg = sp.add_parser("logs"); lg.add_argument("--lines", type=int, default=200); lg.set_defaults(func=cmd_logs)
    cg = sp.add_parser("config-get"); cg.set_defaults(func=cmd_config_get)
    cr = sp.add_parser("config-reload"); cr.set_defaults(func=cmd_config_reload)
    th = sp.add_parser("thresholds"); th.add_argument("--s_open", type=float); th.add_argument("--c_open", type=float); th.add_argument("--p_open", type=float); th.set_defaults(func=cmd_thresholds)
    t = sp.add_parser("test-ai"); t.add_argument("--scenarios", type=int, default=240); t.add_argument("--seed", type=int, default=42); t.add_argument("--blockspec"); t.add_argument("--min-safe-open", type=float, dest="min_safe_open", help="min fraction of safe scenarios that must be OPEN (default 0.6)"); t.set_defaults(func=cmd_test_ai)
    ae = sp.add_parser("act-echo"); ae.add_argument("--actor", default="cli"); ae.add_argument("--message", default="hello-udm"); ae.set_defaults(func=cmd_act_echo)

    args = ap.parse_args()
    if not hasattr(args, "func"):
        ap.print_help(); sys.exit(1)
    try:
        args.func(args)
    except Exception as e:
        print(json.dumps({"error": str(e)})); sys.exit(2)

if __name__ == "__main__":
    main()
