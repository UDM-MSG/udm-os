from typing import Dict, Tuple
import math

class DefaultDriver:
    """
    Default S/C/P computation.
    - If signals provides s/c/p in [0,1], use them.
    - Otherwise, derive coarse values:
      * S: clamp( mean of any 'stability'/'signal_strength'/'ok_rate' ), fallback 0.5
      * C: clamp( 1 - normalized variance proxy ), fallback 0.5
      * P: clamp( error_rate or anomaly proxy ), fallback 0.5
    This is intentionally simple; swap with proper math via registry.
    """
    id = "default"
    version = "1.0.0"

    def _get_first(self, d: Dict, keys, default=None):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return default

    def compute(self, signals: Dict) -> Tuple[float, float, float]:
        # Direct pass-through
        s = self._get_first(signals, ["s", "S"])
        c = self._get_first(signals, ["c", "C"])
        p = self._get_first(signals, ["p", "P"])
        if s is not None and c is not None and p is not None:
            return (float(max(0, min(1, s))),
                    float(max(0, min(1, c))),
                    float(max(0, min(1, p))))

        # Heuristic derivation
        vals = []
        for k in ["stability", "signal_strength", "ok_rate"]:
            if k in signals and signals[k] is not None:
                vals.append(float(signals[k]))
        S = sum(vals)/len(vals) if vals else 0.5
        S = max(0.0, min(1.0, S))

        # crude coherence proxy from spread if samples present
        samples = signals.get("samples") or []
        if isinstance(samples, list) and len(samples) > 1:
            mean = sum(samples)/len(samples)
            var = sum((x-mean)**2 for x in samples)/len(samples)
            # map variance to [0,1] then invert (lower var -> higher C)
            C = 1.0 / (1.0 + var)  # simple squashing
        else:
            C = 0.5
        C = max(0.0, min(1.0, C))

        # pressure proxy
        P = self._get_first(signals, ["error_rate", "pressure", "anomaly_rate"], 0.5)
        P = max(0.0, min(1.0, float(P)))

        return (S, C, P)
