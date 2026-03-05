# UDM - Information Theory Annex

<!--
  UDM Annex
  Auto-generated scaffold on 2026-03-03.
  IMPORTANT: Keep implementation specifics (thresholds, allow-lists, keying/signing details) OUT of annexes.
  Annexes define structure, invariants, interfaces, and test hooks - NOT secrets.
-->
> **Disclosure Policy (Non-Leaking):**
> - No driver equations, weights, or numeric thresholds.
> - No receipt signing internals (algorithms, canonicalization, KIDs, rotation).
> - No real allow-lists, corridor values, or key material.
> - Use symbolic names (e.g., `S_open`, `C_min`) wherever thresholds appear.


**Intent:** Provide an information-theoretic lens for S/C/P and receipts.

### Core Idea (illustrative, symbolic)
- Stability (S) as low drift / bounded divergence.
- Coherence (C) as low internal mismatch.
- Pressure (P) as bounded resource usage intensity.
- Receipts as compact, canonical decision evidence.

## 1. Purpose & Scope
- What this annex formalizes for UDM, and who the target audience is.

## 2. Canonical Mapping to UDM
- **States:** `CLOSED`, `WATCH`, `OPEN`
- **Drivers:** `S` (Stability), `C` (Coherence), `P` (Pressure) in [0,1]
- **Pipeline:** gates -> drivers -> hysteresis -> corridors -> receipt -> `/replay`
- **Principle:** *No receipt, no action.*

## 3. Definitions (Symbols & Terms)
Clearly define any symbols/operators introduced here.

## 4. Model & Invariants (Non-leaking)
- Express structure and properties using symbolic thresholds (e.g., `S_open`, `C_min`, `P_max`, `m` for hysteresis depth).
- Avoid numeric values; keep this implementation-agnostic.

## 5. Interfaces & Test Hooks
- Name relevant API surfaces (e.g., `/gates/plan`, `/govern`, `/replay`) and cross-reference how this annex evaluates or constrains them.
- Include test hooks (what to log, how to assert).

## 6. Safety & Risk Notes
- Boundaries, assumptions, and failure modes relevant to this annex.
- What counts as a violation vs. a warning.

## 7. Worked Examples (Symbolic)
- Small illustrative examples with symbolic parameters, not real numbers.

## 8. Conformance Checklist
- [ ] Uses symbolic thresholds only
- [ ] No secrets present
- [ ] Receipts + `/replay` determinism preserved
- [ ] Annex properties linked to existing L1-L5 tests

## 9. Change Log
- 2026-03-03: Initial scaffold added.
