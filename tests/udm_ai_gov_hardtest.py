# tests/udm_ai_gov_hardtest.py
# "Hard to pass" AI governance test for UDM-OS.
# Simulates AI conditions (agreement/contradiction/hallucination) mapped to S/C/P via the driver interface,
# enforces strict gates so unsafe patterns rarely OPEN. Tunable via env vars.

import os, sys, time, json, argparse, random
from urllib import request, error
from pathlib import Path

def http_json(method, url, body=None, timeout=12.0):
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8", "Connection": "keep-alive"}
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            txt = raw.decode("utf-8") if raw else ""
            try:
                return (json.loads(txt) if txt else {}), resp.status, None
            except Exception:
                return {"_raw": txt}, resp.status, None
    except error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8")), e.code, e
        except Exception:
            return {"error": str(e)}, e.code, e
    except Exception as e:
        return {"error": str(e)}, -1, e

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

def now_ts():
    return int(time.time())


def _parse_block_spec(spec: str):
    """
    Parse "SAFE:3,RISKY:1,SAFE:2" -> [("SAFE",3),("RISKY",1),("SAFE",2)]
    Returns empty list if invalid or empty.
    """
    out = []
    if not spec:
        return out
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            k, v = k.strip().upper(), v.strip()
            try:
                n = int(v)
            except Exception:
                n = 0
        else:
            k, n = p.strip().upper(), 1
        if k not in ("SAFE", "RISKY") or n <= 0:
            continue
        out.append((k, n))
    return out


def _yield_block_sequence(total: int, share: float, block_spec: str, block_rounds: int, seed: int):
    """
    Yield 'SAFE'/'RISKY' labels with a block pattern until 'total' is reached.
    If no valid block_spec provided, fall back to random Bernoulli with risky share.
    """
    r = random.Random(seed)
    pat = _parse_block_spec(block_spec)
    if not pat:
        for _ in range(total):
            yield "RISKY" if r.random() < share else "SAFE"
        return
    unit = []
    for k, n in pat:
        unit.extend([k] * n)
    seq = []
    rounds = max(1, block_rounds)
    while len(seq) < total and rounds > 0:
        seq.extend(unit)
        rounds -= 1
    while len(seq) < total:
        seq.extend(unit)
    seq = seq[:total]
    for x in seq:
        yield x


class Case:
    def __init__(self, name):
        self.name = name
        self.status = "PASS"
        self.details = []
        self.start = time.time()
        self.end = None

    def add(self, msg):
        self.details.append(msg)

    def fail(self, msg):
        self.status = "FAIL"
        self.details.append("FAIL: " + msg)

    def close(self):
        self.end = time.time()

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "details": self.details,
            "duration_s": round((self.end or time.time()) - self.start, 3),
            "ts": now_ts(),
        }


class AIGHardTest:
    """
    Strict policy:
      - Risky scenarios (hi hallucination/contradiction) must NOT OPEN.
      - Safe scenarios should OPEN but only after hysteresis requirements.
      - Overall OPEN rate must stay within configured targets.
    Tunables (env):
      AIG_SCENARIOS=120
      AIG_RISKY_SHARE=0.5         # portion of runs that are risky
      AIG_MAX_RISKY_OPEN=0.02     # <=2% risky OPENs
      AIG_MIN_SAFE_OPEN=0.60      # >=60% safe OPENs
      AIG_SEED=0
    """

    def __init__(self, host):
        self.host = host.rstrip("/")
        self.root = Path(".").resolve()
        self.udm_dir = self.root / "UDM_OS" / ".udm"
        self.reports_dir = self.udm_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.n = env_int("AIG_SCENARIOS", 120)
        self.risky_share = env_float("AIG_RISKY_SHARE", 0.5)
        self.max_risky_open = env_float("AIG_MAX_RISKY_OPEN", 0.02)
        self.min_safe_open = env_float("AIG_MIN_SAFE_OPEN", 0.60)
        self.seed = env_int("AIG_SEED", 0)
        random.seed(self.seed)

        self.safe_total = 0
        self.safe_open = 0
        self.risky_total = 0
        self.risky_open = 0
        self.cases = []

    @staticmethod
    def _map_ai_to_scp(sig):
        """Add s, c, p so default driver (and any driver) gets consistent S/C/P from AI metrics."""
        ok = float(sig.get("ok_rate", 0.5))
        agree = float(sig.get("agreement_score", 0.5))
        err = float(sig.get("error_rate", 0.5))
        lat_var = float(sig.get("latency_var", 0.5))
        viol = float(sig.get("schema_violation_rate", 0.0))
        s = max(0.0, min(1.0, 0.5 + 0.6 * (ok - 0.5) - 0.3 * (lat_var - 0.5)))
        c = max(0.0, min(1.0, 0.5 + 0.6 * (agree - 0.5) - 0.6 * (viol - 0.2)))
        p = max(0.0, min(1.0, 0.5 + 0.7 * (err - 0.5)))
        out = dict(sig)
        out["s"], out["c"], out["p"] = s, c, p
        return out

    def signals_safe(self):
        sig = {
            "agreement_score": 0.88 + random.random() * 0.1,
            "schema_violation_rate": 0.00 + random.random() * 0.05,
            "error_rate": 0.05 + random.random() * 0.05,
            "ok_rate": 0.90 + random.random() * 0.08,
            "latency_var": 0.20 + random.random() * 0.10,
        }
        return self._map_ai_to_scp(sig)

    def signals_risky(self):
        sig = {
            "agreement_score": 0.30 + random.random() * 0.20,
            "schema_violation_rate": 0.45 + random.random() * 0.25,
            "error_rate": 0.35 + random.random() * 0.25,
            "ok_rate": 0.55 + random.random() * 0.20,
            "latency_var": 0.50 + random.random() * 0.25,
        }
        return self._map_ai_to_scp(sig)

    def reset(self):
        http_json("POST", f"{self.host}/admin/hys/reset", {"actor_id": "aig"}, timeout=8.0)

    def step(self, sig):
        j, code, _ = http_json(
            "POST",
            f"{self.host}/govern/v1",
            {"signals": sig, "context": {"scope": "aig", "actor_id": "aig"}},
            timeout=8.0,
        )
        return (j, code)

    def run(self):
        t = Case("AIG.hardtest")

        try:
            self.reset()

            # Block scheduling: AIG_BLOCK_SPEC e.g. "SAFE:3,RISKY:1" gives bursts; else random.
            block_spec = os.getenv("AIG_BLOCK_SPEC", "").strip()
            block_rounds = env_int("AIG_BLOCK_ROUNDS", 0)
            if block_rounds <= 0 and block_spec:
                pat = _parse_block_spec(block_spec)
                unit_len = sum(n for _, n in pat) if pat else 0
                block_rounds = (self.n // unit_len + 1) if unit_len > 0 else 0
            block_rounds = max(1, block_rounds)
            selector = list(_yield_block_sequence(self.n, self.risky_share, block_spec, block_rounds, self.seed))

            for i in range(self.n):
                risky = selector[i] == "RISKY"
                sig = self.signals_risky() if risky else self.signals_safe()
                j, code = self.step(sig)

                if code != 200 or "state" not in j:
                    t.fail(f"govern failed at iter {i}: code={code}, body={j}")
                    continue

                st = j.get("state", "CLOSED")
                if risky:
                    self.risky_total += 1
                    if st == "OPEN":
                        self.risky_open += 1
                else:
                    self.safe_total += 1
                    if st == "OPEN":
                        self.safe_open += 1

            risky_open_rate = (self.risky_open / self.risky_total) if self.risky_total else 0.0
            safe_open_rate = (self.safe_open / self.safe_total) if self.safe_total else 0.0

            t.add(f"safe: {self.safe_open}/{self.safe_total} OPEN -> rate={safe_open_rate:.3f}")
            t.add(f"risky: {self.risky_open}/{self.risky_total} OPEN -> rate={risky_open_rate:.3f}")

            if risky_open_rate > self.max_risky_open + 1e-9:
                t.fail(f"risky OPEN rate too high: {risky_open_rate:.3f} > {self.max_risky_open:.3f}")
            if safe_open_rate < self.min_safe_open - 1e-9:
                t.fail(f"safe OPEN rate too low: {safe_open_rate:.3f} < {self.min_safe_open:.3f}")

        finally:
            t.close()
            self.cases.append(t)

        total = len(self.cases)
        passed = sum(1 for c in self.cases if c.status == "PASS")
        failed = total - passed

        report = {
            "meta": {
                "host": self.host,
                "ts": now_ts(),
                "tool": "udm_ai_gov_hardtest.py",
                "params": {
                    "AIG_SCENARIOS": self.n,
                    "AIG_RISKY_SHARE": self.risky_share,
                    "AIG_MAX_RISKY_OPEN": self.max_risky_open,
                    "AIG_MIN_SAFE_OPEN": self.min_safe_open,
                    "AIG_SEED": self.seed,
                    "AIG_BLOCK_SPEC": os.getenv("AIG_BLOCK_SPEC", ""),
                    "AIG_BLOCK_ROUNDS": env_int("AIG_BLOCK_ROUNDS", 0),
                },
            },
            "summary": {"total": total, "pass": passed, "fail": failed},
            "cases": [c.to_dict() for c in self.cases],
        }

        out = self.reports_dir / f"udm_ai_gov_report_{now_ts()}.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], indent=2))
        print(f"Report saved: {out}")
        return failed


def main():
    ap = argparse.ArgumentParser(description="UDM AI Governance Hard Test")
    ap.add_argument("--host", default=os.getenv("UDM_HOST", "http://localhost:8000"))
    args = ap.parse_args()
    t = AIGHardTest(args.host)
    sys.exit(1 if t.run() > 0 else 0)


if __name__ == "__main__":
    main()
