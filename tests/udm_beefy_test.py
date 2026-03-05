# udm_beefy_test.py
# Comprehensive test harness for UDM OS kernel + regulator split.
# - Smoke: /health, /meta/version, public endpoints
# - Govern: versioned + alias, hysteresis mode transitions
# - Receipts: saved, hashed, /replay verification
# - Planner gates: allowed + disallowed download
# - Simulator: summary check
# - Soak: configurable L4-style burst/backoff loop
# - Report: saves to UDM_OS/.udm/reports/udm_beefy_report_<ts>.json

import json
import os
import sys
import time
import hashlib
import argparse
import random
from pathlib import Path
from urllib import request, error


# -------------------------- Config & Helpers --------------------------

def default_host():
    return os.getenv("UDM_HOST", "http://localhost:8000")


def env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def http_json(method: str, url: str, body=None, timeout=8.0):
    data = None
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Connection": "keep-alive",
    }
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8") if raw else ""
            try:
                j = json.loads(text) if text else {}
            except Exception:
                j = {"_raw": text}
            return j, resp.status, None
    except error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
        except Exception:
            j = {"error": str(e)}
        return j, e.code, e
    except Exception as e:
        return {"error": str(e)}, -1, e


def now_ts():
    return int(time.time())


def sha256_hex_12(obj) -> str:
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


class CaseResult:
    def __init__(self, name):
        self.name = name
        self.status = "PASS"
        self.details = []
        self.started = time.time()
        self.ended = None

    def add(self, msg):
        self.details.append(msg)

    def fail(self, msg):
        self.status = "FAIL"
        self.details.append(f"FAIL: {msg}")

    def end(self):
        self.ended = time.time()

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "details": self.details,
            "duration_s": round((self.ended or time.time()) - self.started, 3),
            "ts": now_ts(),
        }


class BeefyTester:
    def __init__(self, host, iters, burst, backoff, timeout):
        self.host = host.rstrip("/")
        self.iters = iters
        self.burst = burst
        self.backoff = backoff
        self.timeout = timeout
        self.cases = []
        self.errors = 0
        self.repo_root = Path(__file__).resolve().parent
        self.udm_dir = self.repo_root / "UDM_OS" / ".udm"
        self.reports_dir = self.udm_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------- Test Groups ----------------------

    def T0_smoke(self):
        c = CaseResult("T0.smoke")
        try:
            j, code, _ = http_json("GET", f"{self.host}/health", timeout=self.timeout)
            if code != 200 or not j.get("ok"):
                c.fail(f"/health bad response: code={code} body={j}")
            else:
                c.add(f"/health ok v={j.get('version')} hys_depth={j.get('hys_depth')}")

            j2, code, _ = http_json("GET", f"{self.host}/meta/version", timeout=self.timeout)
            if code != 200 or "api_version" not in j2:
                c.fail(f"/meta/version missing api_version: code={code} body={j2}")
            else:
                c.add(f"/meta/version={j2.get('api_version')}")

            j3, code, _ = http_json("GET", f"{self.host}/public/health", timeout=self.timeout)
            if code != 200 or not j3.get("ok", False):
                c.fail(f"/public/health not ok: code={code} body={j3}")

            j4, code, _ = http_json("GET", f"{self.host}/public/state", timeout=self.timeout)
            if code != 200 or "state" not in j4:
                c.fail(f"/public/state bad: code={code} body={j4}")
            else:
                c.add(f"/public/state state={j4.get('state')} hash={j4.get('last_receipt_hash')}")
        finally:
            c.end()
            self.cases.append(c)

    def T1_govern_and_hysteresis(self):
        c = CaseResult("T1.govern_and_hysteresis")
        try:
            j, code, _ = http_json("POST", f"{self.host}/admin/hys/reset", {"actor_id": "test_actor"}, timeout=self.timeout)
            if code != 200:
                c.fail(f"/admin/hys/reset failed: {code} {j}")

            calm = {"s": 0.95, "c": 0.95, "p": 0.05}
            body = {"signals": calm, "context": {"scope": "test", "actor_id": "test_actor"}}
            j2, code, _ = http_json("POST", f"{self.host}/govern/v1", body, timeout=self.timeout)
            if code != 200:
                c.fail(f"/govern/v1 call 1 failed: {code} {j2}")
            state1 = j2.get("state")
            if state1 not in ("WATCH", "OPEN"):
                c.fail(f"Unexpected state after first calm: {state1}")
            c.add(f"1st calm => {state1}")

            j3, code, _ = http_json("POST", f"{self.host}/govern", body, timeout=self.timeout)
            state2 = j3.get("state")
            if code != 200 or state2 != "OPEN":
                c.fail(f"Second calm did not OPEN: {code} {j3}")
            else:
                c.add("2nd calm => OPEN (expected)")

            fault = {"s": 0.90, "c": 0.90, "p": 0.95}
            j4, code, _ = http_json(
                "POST",
                f"{self.host}/govern/v1",
                {"signals": fault, "context": {"scope": "test", "actor_id": "test_actor"}},
                timeout=self.timeout,
            )
            state3 = j4.get("state")
            if code != 200 or state3 != "CLOSED":
                c.fail(f"Fault did not close: {code} {j4}")
            else:
                c.add("Fault => CLOSED (expected)")

            rec = j4.get("receipt") or {}
            rbody = rec.get("receipt_body", {})
            if not rec.get("signature"):
                c.fail("Missing signature in receipt")
            if rbody.get("state") != state3:
                c.fail("Receipt state mismatch")
            reasons = rbody.get("reasons") or {}
            if isinstance(reasons, dict) and "driver_id" not in reasons:
                c.add("Note: no driver_id in reasons (ok if not exposed)")
        finally:
            c.end()
            self.cases.append(c)

    def T2_replay_and_last_hash(self):
        c = CaseResult("T2.replay_and_last_hash")
        try:
            pub1, code, _ = http_json("GET", f"{self.host}/public/state", timeout=self.timeout)
            if code != 200:
                c.fail(f"/public/state failed: {code} {pub1}")
            old_hash = pub1.get("last_receipt_hash")

            body = {"signals": {"s": 0.8, "c": 0.82, "p": 0.2}, "context": {"scope": "test", "actor_id": "hash_actor"}}
            j, code, _ = http_json("POST", f"{self.host}/govern/v1", body, timeout=self.timeout)
            if code != 200:
                c.fail(f"/govern/v1 failed: {code} {j}")
            rec = j.get("receipt") or {}

            rep, code, _ = http_json("POST", f"{self.host}/replay", rec, timeout=self.timeout)
            if code != 200 or not rep.get("valid"):
                c.fail(f"/replay invalid: code={code} body={rep}")
            else:
                c.add(f"/replay valid; hash_12={rep.get('hash_12')}")

            pub2, code, _ = http_json("GET", f"{self.host}/public/state", timeout=self.timeout)
            if code != 200:
                c.fail(f"/public/state (2) failed: {code} {pub2}")
            new_hash = pub2.get("last_receipt_hash")
            if new_hash == old_hash:
                c.fail(f"last_receipt_hash did not change: old={old_hash}, new={new_hash}")
            else:
                c.add(f"last_receipt_hash updated: {old_hash} -> {new_hash}")
        finally:
            c.end()
            self.cases.append(c)

    def T3_gates_plan(self):
        c = CaseResult("T3.gates_plan")
        try:
            plan_ok = {
                "scope": "planner.safe",
                "plan": {
                    "objective": "Fetch safe file",
                    "steps": [],
                    "tools": [],
                    "sources": [],
                    "constraints": {
                        "mask_required": True,
                        "budget": 5,
                        "download": {"url": "https://raw.githubusercontent.com/some/repo/README.md", "save_as": "README.md"},
                    },
                },
            }
            j1, code, _ = http_json("POST", f"{self.host}/gates/plan", plan_ok, timeout=self.timeout)
            if code != 200 or not j1.get("pass", False):
                c.fail(f"Expected pass for allowed domain: {j1}")
            else:
                c.add("Allowed domain passed (expected)")

            plan_bad = {
                "scope": "planner.safe",
                "plan": {
                    "objective": "Fetch bad host",
                    "steps": [],
                    "tools": [],
                    "sources": [],
                    "constraints": {
                        "mask_required": False,
                        "budget": 999,
                        "download": {"url": "https://example.com/evil.bin", "save_as": "evil.bin"},
                    },
                },
            }
            j2, code, _ = http_json("POST", f"{self.host}/gates/plan", plan_bad, timeout=self.timeout)
            if code != 200 or j2.get("pass", True) or not j2.get("violations"):
                c.fail(f"Expected violation for disallowed domain: {j2}")
            else:
                c.add(f"Blocked as expected: {j2.get('violations')}")
        finally:
            c.end()
            self.cases.append(c)

    def T4_simulator(self):
        c = CaseResult("T4.simulator")
        try:
            payload = {
                "iters": 25,
                "signals": [
                    {"s": 0.9, "c": 0.9, "p": 0.1},
                    {"s": 0.95, "c": 0.8, "p": 0.2},
                    {"s": 0.5, "c": 0.6, "p": 0.7},
                    {"s": 0.85, "c": 0.86, "p": 0.15},
                ],
            }
            j, code, _ = http_json("POST", f"{self.host}/simulate/govern", payload, timeout=max(self.timeout, 12.0))
            if code != 200 or "summary" not in j:
                c.fail(f"/simulate/govern failed or malformed: {code} {j}")
            else:
                c.add(f"simulate summary: {j.get('summary')}")
        finally:
            c.end()
            self.cases.append(c)

    def T5_soak(self):
        c = CaseResult("T5.soak")
        try:
            iters = self.iters
            burst = max(1, self.burst)
            backoff = self.backoff
            modes = {"CLOSED": 0, "WATCH": 0, "OPEN": 0}
            failures = 0
            http_json("POST", f"{self.host}/admin/hys/reset", {"actor_id": "soak"}, timeout=self.timeout)

            for i in range(iters):
                if i % 27 == 0 and i > 0:
                    sig = {"s": 0.9, "c": 0.9, "p": 0.95}
                else:
                    sig = {
                        "s": 0.70 + random.random() * 0.3,
                        "c": 0.72 + random.random() * 0.25,
                        "p": 0.08 + random.random() * 0.25,
                    }
                j, code, err = http_json(
                    "POST",
                    f"{self.host}/govern/v1",
                    {"signals": sig, "context": {"scope": "soak", "actor_id": "soak"}},
                    timeout=self.timeout,
                )
                if code != 200:
                    failures += 1
                else:
                    st = j.get("state", "CLOSED")
                    modes[st] = modes.get(st, 0) + 1

                if (i + 1) % burst == 0:
                    time.sleep(backoff)

            c.add(f"modes={modes}, failures={failures}, iters={iters}, burst={burst}, backoff={backoff}")
            if failures > 0.02 * iters:
                c.fail(f"Failure rate too high: {failures}/{iters}")
        finally:
            c.end()
            self.cases.append(c)

    def T6_usc(self):
        """USC: echo connector + idempotency + TTL (no internet)."""
        c = CaseResult("T6.usc_actuate_echo_idempotency")
        try:
            http_json("POST", f"{self.host}/admin/hys/reset", {"actor_id": "usc"}, timeout=self.timeout)
            calm = {"s": 0.95, "c": 0.95, "p": 0.05}
            j1, code, _ = http_json(
                "POST", f"{self.host}/govern/v1",
                {"signals": calm, "context": {"scope": "usc", "actor_id": "usc"}},
                timeout=self.timeout,
            )
            if code != 200:
                c.fail(f"prep govern 1 failed: {code} {j1}")
            j2, code, _ = http_json(
                "POST", f"{self.host}/govern/v1",
                {"signals": calm, "context": {"scope": "usc", "actor_id": "usc"}},
                timeout=self.timeout,
            )
            if code != 200 or j2.get("state") != "OPEN":
                c.fail(f"prep govern 2 not OPEN: {code} {j2}")
            rec = j2.get("receipt") or {}
            action_id = f"echo-{int(time.time())}"
            env = {
                "receipt": rec,
                "action": {"type": "echo", "params": {"message": "hello-usc"}, "action_id": action_id, "ttl_s": 120},
            }
            a1, code, _ = http_json("POST", f"{self.host}/actuate", env, timeout=self.timeout)
            if code != 200 or not a1.get("ok"):
                c.fail(f"/actuate echo failed: {code} {a1}")
            a2, code, _ = http_json("POST", f"{self.host}/actuate", env, timeout=self.timeout)
            if code != 200 or not a2.get("ok") or not a2.get("idempotent", False):
                c.fail(f"/actuate idempotency failed: {code} {a2}")
            env_bad = {
                "receipt": rec,
                "action": {"type": "echo", "params": {"message": "late"}, "action_id": action_id + "-late", "ttl_s": -1},
            }
            a3, code, _ = http_json("POST", f"{self.host}/actuate", env_bad, timeout=self.timeout)
            if code == 200:
                c.fail("TTL check should reject ttl_s=-1")
        finally:
            c.end()
            self.cases.append(c)

    # ---------------------- Runner & Report ----------------------

    def run_all(self):
        start = time.time()
        self.T0_smoke()
        self.T1_govern_and_hysteresis()
        self.T2_replay_and_last_hash()
        self.T3_gates_plan()
        self.T4_simulator()
        self.T5_soak()
        self.T6_usc()
        end = time.time()

        total = len(self.cases)
        passed = sum(1 for x in self.cases if x.status == "PASS")
        failed = total - passed

        report = {
            "meta": {
                "host": self.host,
                "ts": now_ts(),
                "duration_s": round(end - start, 3),
                "tool": "udm_beefy_test.py",
            },
            "summary": {"total": total, "pass": passed, "fail": failed},
            "cases": [c.to_dict() for c in self.cases],
        }

        ts = now_ts()
        out = self.reports_dir / f"udm_beefy_report_{ts}.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print(json.dumps(report["summary"], indent=2))
        print(f"Report saved: {out}")
        if failed > 0:
            for c in self.cases:
                if c.status != "PASS":
                    print(f"[FAIL] {c.name}: {c.details[-1] if c.details else ''}")
        return failed


# -------------------------- CLI --------------------------

def main():
    ap = argparse.ArgumentParser(description="UDM OS beefy test runner")
    ap.add_argument("--host", default=default_host(), help="Kernel host (default: http://localhost:8000)")
    ap.add_argument("--iters", type=int, default=env_int("UDM_L4_ITERS", 140), help="Soak iterations")
    ap.add_argument("--burst", type=int, default=env_int("UDM_L4_BURST", 25), help="Burst length before backoff sleep")
    ap.add_argument("--backoff", type=float, default=env_float("UDM_L4_BACKOFF", 0.004), help="Seconds to sleep per burst")
    ap.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout seconds")
    args = ap.parse_args()

    t = BeefyTester(args.host, args.iters, args.burst, args.backoff, args.timeout)
    failed = t.run_all()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
