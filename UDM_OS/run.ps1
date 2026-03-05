param()
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$Port = if ($env:UDM_PORT) { [int]$env:UDM_PORT } else { 8000 }
# If port already in use, assume kernel is already running — exit cleanly.
$inUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host "Port $Port already in use (kernel likely running). Exiting. Use http://localhost:$Port"
    exit 0
}
# Dev-only default; for public/production set UDM_ACTIVE_SECRET in env (e.g. .\tools\gen_secret.ps1)
if (-not $env:UDM_ACTIVE_SECRET) { $env:UDM_ACTIVE_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" }
if (-not $env:UDM_ADMIN_TOKEN) {
    Write-Host ""
    Write-Host "UDM_ADMIN_TOKEN is not set. /admin/* and /tests/ai_gov/* will return 403." -ForegroundColor Yellow
    Write-Host "To fix: stop this kernel (Ctrl+C), then run: " -NoNewline -ForegroundColor Yellow
    Write-Host "`$env:UDM_ADMIN_TOKEN = (.\tools\gen_secret.ps1); .\run_kernel.ps1 -Restart" -ForegroundColor Cyan
    Write-Host "(From repo root. Use the same token in the dashboard and in scripts.)" -ForegroundColor DarkGray
    Write-Host ""
}
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.kernel_app:app --host 0.0.0.0 --port $Port --reload
# ---- UDM OS defaults (added by refactor) ----
# UDM OS environment defaults (safe to re-apply)
if (-not $env:UDM_ACTIVE_SECRET) { $env:UDM_ACTIVE_SECRET = ("0123456789abcdef" * 4) }  # replace in prod
if (-not $env:UDM_API_VERSION)  { $env:UDM_API_VERSION  = "1.0.0" }
if (-not $env:UDM_DRIVER_ACTIVE){ $env:UDM_DRIVER_ACTIVE = "default" }

# Thresholds (align to your canon; tune as needed)
if (-not $env:UDM_S_MIN)  { $env:UDM_S_MIN  = "0.70" }
if (-not $env:UDM_C_MIN)  { $env:UDM_C_MIN  = "0.75" }
if (-not $env:UDM_P_MAX)  { $env:UDM_P_MAX  = "0.30" }
if (-not $env:UDM_S_OPEN) { $env:UDM_S_OPEN = "0.72" }
if (-not $env:UDM_C_OPEN) { $env:UDM_C_OPEN = "0.77" }
if (-not $env:UDM_P_OPEN) { $env:UDM_P_OPEN = "0.28" }
if (-not $env:UDM_HYS_M)  { $env:UDM_HYS_M  = "2" }
