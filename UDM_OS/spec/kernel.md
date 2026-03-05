# Kernel Specification (Stable Contract)

Version: udm-core v1.0.3

States:
- CLOSED  - block actuation; ASK/EXPLAIN only
- WATCH   - in-band but stabilizing; not yet allowed to act
- OPEN    - allowed to act within a bounded corridor

Drivers:
- S (Stability)  = 1 - burst (example mapping)
- C (Coherence)  = 1 - err_rate
- P (Pressure)   = normalized QPS

Policy thresholds:
- S_min = 0.70
- C_min = 0.75
- P_max = 0.30

Enter-open gates (strict):
- S_open = 0.72
- C_open = 0.77
- P_open = 0.28

Hysteresis:
- depth m=2 in-band windows (recent_inband = [(S,C,P), (S,C,P)])
- promotion to OPEN requires m consecutive strict in-band windows
- any violation clears memory and returns to CLOSED

Transitions:
- * -> CLOSED on any violation
- CLOSED -> WATCH after 1 in-band calm window
- WATCH  -> OPEN  after the 2nd consecutive strict in-band window

Reasons (labels):
- S_LOW, C_LOW, P_HIGH, IN_BAND_NOT_STABLE, HYST_OK

Corridor:
- In OPEN, constrain outputs by corridor (length, claims, style).
  In WATCH/CLOSED, only ASK/EXPLAIN.
