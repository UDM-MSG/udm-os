# UDM Â· 01234 Architecture Cheatâ€‘Sheet

**0 â€” Context & Constraints (OS)**: actors, scopes, budgets, allowâ€‘lists, driver profile, threshold set  
**1 â€” Sense (Core)**: raw signals â†’ S (Stability), C (Coherence), P (Pressure)  
**2 â€” Decide (Core)**: thresholds (s_min, c_min, p_max, s_open, c_open, p_open); hysteresis depth m; faultâ€‘close  
**3 â€” Act (OS)**: Safety Conduit; "No receipt â†’ No action"; planâ€‘gate, idempotency, rate/budget, integrity  
**4 â€” Audit & Replay (OS)**: signed receipts (HMAC), /replay verification, public state, event logs

**State Logic**

*   **OPEN**: Sâ‰¥s_open, Câ‰¥c_open, Pâ‰¤p_open, and **m** calm windows satisfied
*   **WATCH**: above fault thresholds but not yet calm enough
*   **CLOSED**: S<s_min or C<c_min or P>p_max (or explicit fault/reset)

**Exchange**

*   Core â†’ OS: decision body (state + reasons: S/C/P + hysteresis)
*   OS â†’ Core: (none); OS signs decision â†’ receipt â†’ public state; /actuate requires valid receipt
