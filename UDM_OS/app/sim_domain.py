# UDM_OS/app/sim_domain.py
# Domain simulators: AI, Weather, Traffic — signal generators with S/C/P mapping.

import random
import math
from typing import Dict, List, Optional

def _rng(seed: Optional[int]):
    r = random.Random()
    if seed is not None:
        r.seed(int(seed))
    return r

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def _map_ai_to_scp(sig: Dict) -> Dict:
    ok = float(sig.get("ok_rate", 0.5))
    agree = float(sig.get("agreement_score", 0.5))
    err = float(sig.get("error_rate", 0.5))
    lat_var = float(sig.get("latency_var", 0.5))
    S = _clamp01(0.5 + 0.6 * (ok - 0.5) - 0.3 * (lat_var - 0.5))
    viol = float(sig.get("schema_violation_rate", 0.0))
    C = _clamp01(0.5 + 0.6 * (agree - 0.5) - 0.6 * (viol - 0.2))
    qg = float(sig.get("queue_growth", 0.0))
    P = _clamp01(0.5 + 0.7 * (err - 0.5) + 0.4 * qg)
    sig = dict(sig)
    sig.update({"s": S, "c": C, "p": P})
    return sig

def _map_weather_to_scp(sig: Dict) -> Dict:
    inst = float(sig.get("instability_index", 0.5))
    agree = float(sig.get("model_agreement", 0.5))
    hazard = float(sig.get("hazard_index", 0.5))
    S = _clamp01(1.0 - inst * 0.8)
    C = _clamp01(0.3 + 0.7 * agree)
    P = _clamp01(0.2 + 0.8 * hazard)
    sig = dict(sig)
    sig.update({"s": S, "c": C, "p": P})
    return sig

def _map_traffic_to_scp(sig: Dict) -> Dict:
    spd = float(sig.get("flow_speed_norm", 0.5))
    agree = float(sig.get("sensor_agreement", 0.5))
    inc = float(sig.get("incident_rate", 0.5))
    qg = float(sig.get("queue_growth", 0.0))
    S = _clamp01(0.2 + 0.8 * spd - 0.3 * inc - 0.2 * qg)
    C = _clamp01(0.3 + 0.7 * agree - 0.2 * inc)
    P = _clamp01(0.2 + 0.6 * inc + 0.5 * qg)
    sig = dict(sig)
    sig.update({"s": S, "c": C, "p": P})
    return sig

def ai_signals(iters: int = 50, mode: str = "random", seed: Optional[int] = None) -> List[Dict]:
    r = _rng(seed)
    seq: List[Dict] = []
    for i in range(int(iters)):
        if mode == "safe":
            sig = {
                "agreement_score": 0.85 + 0.1 * r.random(),
                "schema_violation_rate": 0.00 + 0.05 * r.random(),
                "error_rate": 0.05 + 0.05 * r.random(),
                "ok_rate": 0.90 + 0.08 * r.random(),
                "latency_var": 0.20 + 0.10 * r.random(),
            }
        elif mode == "risky":
            sig = {
                "agreement_score": 0.30 + 0.20 * r.random(),
                "schema_violation_rate": 0.45 + 0.25 * r.random(),
                "error_rate": 0.35 + 0.25 * r.random(),
                "ok_rate": 0.55 + 0.20 * r.random(),
                "latency_var": 0.50 + 0.25 * r.random(),
            }
        elif mode == "drift":
            t = i / max(1, (iters - 1))
            sig = {
                "agreement_score": _clamp01(0.95 - 0.6 * t + 0.05 * r.random()),
                "schema_violation_rate": _clamp01(0.02 + 0.6 * t + 0.05 * r.random()),
                "error_rate": _clamp01(0.06 + 0.6 * t + 0.05 * r.random()),
                "ok_rate": _clamp01(0.92 - 0.4 * t + 0.05 * r.random()),
                "latency_var": _clamp01(0.22 + 0.3 * t + 0.05 * r.random()),
            }
        else:
            if r.random() < 0.5:
                sig = {
                    "agreement_score": 0.8 + 0.15 * r.random(),
                    "schema_violation_rate": 0.00 + 0.12 * r.random(),
                    "error_rate": 0.05 + 0.15 * r.random(),
                    "ok_rate": 0.85 + 0.14 * r.random(),
                    "latency_var": 0.15 + 0.20 * r.random(),
                }
            else:
                sig = {
                    "agreement_score": 0.35 + 0.30 * r.random(),
                    "schema_violation_rate": 0.35 + 0.35 * r.random(),
                    "error_rate": 0.25 + 0.35 * r.random(),
                    "ok_rate": 0.55 + 0.35 * r.random(),
                    "latency_var": 0.40 + 0.35 * r.random(),
                }
        seq.append(_map_ai_to_scp(sig))
    return seq

def weather_signals(iters: int = 50, mode: str = "random", seed: Optional[int] = None) -> List[Dict]:
    r = _rng(seed)
    seq: List[Dict] = []
    for i in range(int(iters)):
        if mode == "calm":
            inst = 0.10 + 0.10 * r.random()
            agree = 0.80 + 0.15 * r.random()
            hazard = 0.05 + 0.10 * r.random()
        elif mode == "stormy":
            inst = 0.70 + 0.25 * r.random()
            agree = 0.40 + 0.20 * r.random()
            hazard = 0.60 + 0.35 * r.random()
        elif mode == "front":
            t = i / max(1, (iters - 1))
            inst = _clamp01(0.20 + 0.8 * math.sin(2.8 * t + 0.2 * r.random()) * 0.5 + 0.3 * t)
            agree = _clamp01(0.85 - 0.6 * t + 0.1 * r.random())
            hazard = _clamp01(0.10 + 0.8 * t + 0.1 * r.random())
        else:
            inst = r.random()
            agree = 0.3 + 0.7 * r.random()
            hazard = r.random()
        sig = {"instability_index": inst, "model_agreement": agree, "hazard_index": hazard}
        seq.append(_map_weather_to_scp(sig))
    return seq

def traffic_signals(iters: int = 50, mode: str = "random", seed: Optional[int] = None) -> List[Dict]:
    r = _rng(seed)
    seq: List[Dict] = []
    for i in range(int(iters)):
        if mode == "freeflow":
            spd = 0.80 + 0.20 * r.random()
            agree = 0.75 + 0.20 * r.random()
            inc = 0.02 + 0.06 * r.random()
            qg = 0.00 + 0.05 * r.random()
        elif mode == "rush":
            spd = 0.30 + 0.25 * r.random()
            agree = 0.50 + 0.25 * r.random()
            inc = 0.10 + 0.20 * r.random()
            qg = 0.20 + 0.30 * r.random()
        elif mode == "incident":
            spd = 0.20 + 0.20 * r.random()
            agree = 0.40 + 0.25 * r.random()
            inc = 0.30 + 0.40 * r.random()
            qg = 0.35 + 0.40 * r.random()
        else:
            spd = r.random()
            agree = 0.3 + 0.7 * r.random()
            inc = r.random()
            qg = r.random() * 0.8
        sig = {"flow_speed_norm": spd, "sensor_agreement": agree, "incident_rate": inc, "queue_growth": qg}
        seq.append(_map_traffic_to_scp(sig))
    return seq

SIMS = {
    "ai": {"modes": ["safe", "risky", "drift", "random"], "fn": ai_signals},
    "weather": {"modes": ["calm", "stormy", "front", "random"], "fn": weather_signals},
    "traffic": {"modes": ["freeflow", "rush", "incident", "random"], "fn": traffic_signals},
}
