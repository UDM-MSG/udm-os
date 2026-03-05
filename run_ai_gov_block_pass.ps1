# run_ai_gov_block_pass.ps1
# Run AI Governance Hard Test in block mode (SAFE/RISKY bursts) for m=2 calm-window-friendly stimulus.
param(
    [int]$Scenarios = 240,
    [string]$BlockSpec = "SAFE:3,RISKY:1",
    [int]$BlockRounds = 0,   # 0 = auto
    [double]$MaxRiskyOpen = 0.02,
    [double]$MinSafeOpen = 0.60,
    [int]$Seed = 42
)
if (-not $env:UDM_ADMIN_TOKEN) {
    Write-Host "Set UDM_ADMIN_TOKEN first (e.g. from run_udm_ai_gov_pass.ps1 or tools\gen_secret.ps1)." -ForegroundColor Red
    exit 1
}
$port = if ($env:UDM_PORT) { $env:UDM_PORT } else { "8000" }
$body = @{
    admin_token        = $env:UDM_ADMIN_TOKEN
    AIG_SCENARIOS      = $Scenarios
    AIG_RISKY_SHARE    = 0.5
    AIG_MAX_RISKY_OPEN = $MaxRiskyOpen
    AIG_MIN_SAFE_OPEN  = $MinSafeOpen
    AIG_SEED           = $Seed
    AIG_EXPLAIN        = 1
    AIG_BLOCK_SPEC     = $BlockSpec
    AIG_BLOCK_ROUNDS   = $BlockRounds
} | ConvertTo-Json
try {
    $r = Invoke-RestMethod -Uri "http://localhost:$port/tests/ai_gov/run_blocks" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 900
    if ($r.output) { Write-Host $r.output }
    if ($r.ok) { Write-Host "PASS" -ForegroundColor Green } else { Write-Host "FAIL (returncode $($r.returncode))" -ForegroundColor Red }
} catch {
    $msg = $_.Exception.Message
    $details = ""
    if ($_.ErrorDetails) { $details = $_.ErrorDetails.Message }
    $is403 = ($msg -match "403|Forbidden") -or ($details -match "forbidden")
    if ($is403) {
        Write-Host "Kernel returned 403 Forbidden." -ForegroundColor Red
        Write-Host "Set UDM_ADMIN_TOKEN in this window to the same value used when you started the kernel, then run again." -ForegroundColor Yellow
        Write-Host "Example: `$env:UDM_ADMIN_TOKEN = '<same-token-as-kernel>'; .\run_ai_gov_block_pass.ps1 -Scenarios 240 -BlockSpec 'SAFE:3,RISKY:1' -Seed 42" -ForegroundColor Gray
    } else {
        Write-Host "Request failed: $msg" -ForegroundColor Red
        if ($details) { Write-Host $details -ForegroundColor Red }
    }
    exit 1
}
