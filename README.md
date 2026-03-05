# UDM-OS (Open Source Bundle)

**What this includes**
- **UDM Core** (S/C/P â†’ Hysteresis â†’ State)
- **Govern Shell (OS)** (govern, gates, actuate, replay, public state)
- **Drivers** (Default, Emergent; plugin loader)
- **Safe connectors** (echo, download via USC)
- **Tests** (beefy test, AI Governance Hard Test)
- **01234 DSL cheatâ€‘sheet** (docs/UDM_01234_CheatSheet.md)
- **SDK (Python)** (sdk/udm_sdk.py)
- **Dashboards** (if provided)

**What this does NOT include**
- No secrets or tokens
- No `.udm/` state, receipts, delivery logs, downloads
- No personal configs (actors.json, config.yaml)

## Quick Start

```powershell
# From repo root
$env:UDM_ADMIN_TOKEN = (.\tools\gen_secret.ps1)
.\run_kernel.ps1

# Sanity
python .\udmctl.py status
curl -s http://localhost:8000/public/state

# Run strict governance test (block-scheduled)
python .\udmctl.py test-ai --scenarios 240 --seed 42 --blockspec "SAFE:3,RISKY:1"
```

## Safe Actuation (USC)

*   **No receipt â†’ No action**
*   Planâ€‘gate â†’ allowâ€‘lists, budgets, flags
*   Idempotency, rateâ€‘limits, integrity (hash) checks
*   Delivery receipts linking actions to decisions

## Endpoints

*   `POST /gates/plan`
*   `POST /govern` (alias for `/govern/v1`)
*   `POST /actuate`
*   `POST /replay`
*   `GET  /public/state`
*   `POST /admin/hys/reset` (adminâ€‘token)
*   `POST /tests/ai_gov/run` and `/tests/ai_gov/run_blocks` (if present)

## License

See **LICENSE**. You may choose MIT/Apacheâ€‘2.0/BSDâ€‘3â€‘Clause or another permissive license.

## Security

*   Never commit tokens or `.udm/` data.
*   Receipts contain S/C/P and state only, not private content.
*   Use allowâ€‘lists and hashes for downloads.
