# Run UDM beefy test from project root.
# Prerequisite: kernel must be running (e.g. .\run_kernel.ps1 or cd UDM_OS; python -m uvicorn app.kernel_app:app --host 127.0.0.1 --port 8000)
# Usage: .\run_beefy_test.ps1
#   Or with args: .\run_beefy_test.ps1 -Iters 150 -Burst 25 -Backoff 0.004

param(
    [string]$HostUrl = $env:UDM_HOST,
    [int]$Iters = 150,
    [int]$Burst = 25,
    [double]$Backoff = 0.004,
    [double]$Timeout = 8.0
)

if (-not $HostUrl) { $HostUrl = "http://localhost:8000" }

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

& python udm_beefy_test.py --host $HostUrl --iters $Iters --burst $Burst --backoff $Backoff --timeout $Timeout
exit $LASTEXITCODE
