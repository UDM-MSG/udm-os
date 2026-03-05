# Evidence Guide (Proving UDM Works)

**Goal**: produce a small, verifiable pack others can repeat.

1.  **Health + thresholds**

```powershell
python .\udmctl.py status
python .\udmctl.py config-get
```

2.  **Run hard test (strict)**

```powershell
python .\udmctl.py test-ai --scenarios 240 --seed 42 --blockspec "SAFE:3,RISKY:1"
```

The test prints a report path under `UDM_OS\.udm\reports\...json`.

3.  **Replay last receipt**

```powershell
python .\udmctl.py replay-last    # expect: valid:true
```

4.  **Optional: Package**
    Copy health.json, thresholds.json, latest report, log tail â†’ `docs/evidence/`.

**Note**: Never include `.udm/` receipts or any tokens in public repos.
