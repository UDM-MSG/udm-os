# UDM - Human Understanding (People's Edition)

<!--
  UDM Annex
  Auto-generated on 2026-03-04.
  Annexes are non-leaking: no thresholds, keys, allow-lists, driver equations.
  They define structure, invariants, interfaces, symbolic variables, and test hooks only.
-->
> **Disclosure Policy (Non-Leaking):**
> - No driver equations, weights, or numeric thresholds.
> - No signing internals (algorithms, fields, KIDs, rotation).
> - No real allow-lists, corridor values, or secrets.
> - Use symbolic names (e.g., `S_open`, `C_min`, `P_max`, `m`) wherever needed.


**Goal:** Explain UDM in plain language (traffic lights, cooking, home safety). CLOSED = stop; WATCH = getting ready; OPEN = safe to do. S/C/P as health/consistency/stress. No math.

## 1. Purpose & Scope
Describe the aim of this annex and who it serves.

## 2. Canonical Mapping to UDM
- **States:** `CLOSED`, `WATCH`, `OPEN`
- **Drivers:** `S` (Stability), `C` (Coherence), `P` (Pressure) in [0,1]
- **Lifecycle:** Gates -> Drivers -> Hysteresis -> Corridors -> Receipt -> `/replay`
- **Rule:** *No receipt, no action.*

## 3. Definitions (Symbols & Terms)
Define any symbols/operators introduced here (symbolic only).

## 4. Model & Invariants (Non-leaking)
Use symbolic thresholds (e.g., `S_open`, `C_min`, `P_max`, `m`); avoid numbers.

## 5. Interfaces & Test Hooks
Reference endpoints (e.g., `/gates/plan`, `/govern`, `/replay`) and what to assert.

## 6. Safety & Risk Notes
Boundaries, assumptions, and violation semantics.

## 7. Worked Examples (Symbolic)
Small examples with symbolic parameters - not real numbers.

## 8. Conformance Checklist
- [ ] Symbolic thresholds only
- [ ] No secrets present
- [ ] Receipts + `/replay` determinism preserved
- [ ] Annex assertions linked to L1-L5 test packs

## 9. Change Log
- 2026-03-04: Initial scaffold
