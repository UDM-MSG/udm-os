import os
from dataclasses import dataclass

def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

@dataclass
class Hysteresis:
    s_min: float = _f("UDM_S_MIN", 0.70)
    c_min: float = _f("UDM_C_MIN", 0.75)
    p_max: float = _f("UDM_P_MAX", 0.30)
    s_open: float = _f("UDM_S_OPEN", 0.72)
    c_open: float = _f("UDM_C_OPEN", 0.77)
    p_open: float = _f("UDM_P_OPEN", 0.28)
    m: int = int(os.getenv("UDM_HYS_M", "2"))
    calm_windows: int = 0
    mode: str = "CLOSED"  # CLOSED / WATCH / OPEN

    def update(self, S: float, C: float, P: float):
        # Fault close
        if (S < self.s_min) or (C < self.c_min) or (P > self.p_max):
            self.mode = "CLOSED"
            self.calm_windows = 0
            return {"reason": "fault_close", "mode": self.mode}

        # Calm window accounting
        if (S >= self.s_open) and (C >= self.c_open) and (P <= self.p_open):
            self.calm_windows += 1
        else:
            self.calm_windows = max(0, self.calm_windows - 1)
            if self.mode == "OPEN" and self.calm_windows < self.m:
                self.mode = "WATCH"

        # Enter OPEN after m calm windows
        if self.calm_windows >= self.m:
            self.mode = "OPEN"
        elif self.mode != "OPEN":
            self.mode = "WATCH"

        return {"reason": "update", "mode": self.mode}

    def reset(self):
        self.calm_windows = 0
        self.mode = "CLOSED"
