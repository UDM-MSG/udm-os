# Receipt Specification (Deterministic Replay)

Key: receipt_body.version = "1.0.3"

Each receipt MUST include:
- version, policy, signals, window, state, reasons
- drivers: S, C, P (rounded consistently)
- hysteresis: depth, recent_inband, enter_open thresholds
- context: scope, actor_id, env
- content: input_type, text

Canonicalization:
- JSON UTF-8, stable key order (JCS-like)
- numeric rounding: 6 decimals for floats
- reasons sorted lexicographically

Signature envelope:
- { "receipt_body": <obj>, "signature": <hex>, "signed": true|false }

Replay procedure:
1) verify signature (if present); reject if mismatch
2) restore policy, drivers (S,C,P), hysteresis (depth, recent_inband, enter_open)
3) recompute state and reasons from restored snapshot
4) match requires identical state + reasons
