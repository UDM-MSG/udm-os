# UDM_OS/app/drivers/emergent.py
from typing import Dict, Tuple

class EmergentDriver:
    """
    Emergent (auto-mapped) driver:
    - Produces S/C/P in [0,1] from generic signals with simple, interpretable weights.
    - Includes safety rails (clamps + rule caps/floors).
    - Learning stub via update_from_batch (off by default).
    """
    id = "emergent"
    version = "0.1.0"

    def __init__(self):
        self.w = {
            "ok_rate->S": 0.6,
            "latency_var->S": -0.3,
            "agreement->C": 0.5,
            "schema_viol->C": -0.5,
            "error_rate->P": 0.7,
            "queue_growth->P": 0.4,
        }

    def _clamp01(self, x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    def compute(self, signals: Dict) -> Tuple[float, float, float]:
        ok = float(signals.get("ok_rate", signals.get("s", 0.5)))
        lat_var = float(signals.get("latency_var", 0.5))
        agreement = float(signals.get("agreement_score", 0.5))
        schema_viol = float(signals.get("schema_violation_rate", 0.0))
        err = float(signals.get("error_rate", signals.get("p", 0.5)))
        qg = float(signals.get("queue_growth", 0.0))

        S = self._clamp01(0.5 + self.w["ok_rate->S"] * (ok - 0.5) + self.w["latency_var->S"] * (lat_var - 0.5))
        C = self._clamp01(0.5 + self.w["agreement->C"] * (agreement - 0.5) + self.w["schema_viol->C"] * (schema_viol - 0.5))
        P = self._clamp01(0.5 + self.w["error_rate->P"] * (err - 0.5) + self.w["queue_growth->P"] * (qg - 0.0))

        if err > 0.30:
            P = max(P, 0.60)
        if schema_viol > 0.40:
            C = min(C, 0.40)

        return (S, C, P)

    def update_from_batch(self, batch_stats: Dict):
        try:
            t = (batch_stats or {}).get("target") or {}
            tgtS = float(t.get("S", 0.5))
            tgtC = float(t.get("C", 0.5))
            tgtP = float(t.get("P", 0.5))

            ok = float(batch_stats.get("ok_rate", 0.5))
            lat_var = float(batch_stats.get("latency_var", 0.5))
            agreement = float(batch_stats.get("agreement_score", 0.5))
            schema_viol = float(batch_stats.get("schema_violation_rate", 0.0))
            err = float(batch_stats.get("error_rate", 0.5))
            qg = float(batch_stats.get("queue_growth", 0.0))

            S, C, P = self.compute({
                "ok_rate": ok, "latency_var": lat_var,
                "agreement_score": agreement, "schema_violation_rate": schema_viol,
                "error_rate": err, "queue_growth": qg,
            })

            step = 0.05
            self.w["ok_rate->S"] += step * (tgtS - S) * (ok - 0.5)
            self.w["latency_var->S"] += step * (tgtS - S) * (lat_var - 0.5) * (-1.0)
            self.w["agreement->C"] += step * (tgtC - C) * (agreement - 0.5)
            self.w["schema_viol->C"] += step * (tgtC - C) * (-(schema_viol - 0.5))
            self.w["error_rate->P"] += step * (tgtP - P) * (err - 0.5)
            self.w["queue_growth->P"] += step * (tgtP - P) * (qg - 0.0)

            for key in list(self.w.keys()):
                self.w[key] = float(max(-1.0, min(1.0, self.w[key])))
            return {"ok": True, "updated_weights": dict(self.w)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
