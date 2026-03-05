# UDM – Weather Annex

> **Status:** Placeholder  
> **Version:** 0.1.0  
> **Date:** 2026-03-04

## 1) Purpose
Describe how **Weather** maps into the UDM OS regulator. This annex explains the domain signals and how they compress into **S/C/P** -> **OPEN/WATCH/CLOSED** decisions with receipts and replay.

## 2) Signals -> S/C/P (bounded in [0,1])
- **Stability (S)**: pressure/temperature trend stability, variance of key fields, forecast persistence
- **Coherence (C)**: model agreement (ensemble consensus), station-to-grid agreement, temporal consistency
- **Pressure (P)**: hazard indices (storm/precip/gust), rapid change rates, alert density

**Driver intent:** produce three bounded values:
- **S (stability):** 0 (unstable) -> 1 (highly stable)  
- **C (coherence):** 0 (incoherent) -> 1 (highly coherent)  
- **P (pressure):** 0 (no pressure) -> 1 (high pressure)

## 3) Example driver features (sketch)
- Deterministic feature layer -> bounded linear/logistic transforms -> clamp to [0,1]
- Monotonic constraints where applicable (e.g., higher error -> higher P)
- Shadow evaluation before promotion to active driver

## 4) Thresholds and hysteresis (defaults, tune per deployment)
- S_min=0.70, C_min=0.75, P_max=0.30  
- Enter-OPEN thresholds: S>=0.72, C>=0.77, P<=0.28  
- Hysteresis depth m=2 calm windows (adjust for the domain)

## 5) State semantics for Weather
- OPEN: allow downstream weather-dependent operations (e.g., plan outdoor tasks, trigger advisory info)
- WATCH: caution posture (buffer schedules, limit risky operations, increase monitoring)
- CLOSED: suspend hazardous operations; prioritize alerts and protective actions

## 6) Actions gating and receipts
- **No receipt, no action**: actions must be gated by an **OPEN** state and a valid signed receipt
- All decisions are recorded: .udm/receipts/*.json and .udm/last_receipt.json
- /replay validates signatures; /public/state exposes last hash for observability

## 7) Safety and policy notes
- Add domain-specific policies here (privacy, compliance, allowed tools/sources)
- Use /gates/plan to check downloads, budgets, and tool constraints before acting

## 8) Future work
- Expand driver feature set and calibration procedures
- Add domain simulators under /simulate/* for this annex
- Document promotion gates and validation datasets
