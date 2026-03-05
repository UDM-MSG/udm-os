# udm_doctor.ps1
# UDM Doctor: clean-restart kernel, verify health, and run the AI Governance Hard Test.
# Run from repo root (folder containing UDM_OS/).
# Usage:
#   .\udm_doctor.ps1
#   .\udm_doctor.ps1 -Scenarios 240 -Seed 42 -BlockSpec "SAFE:3,RISKY:1"
#   .\udm_doctor.ps1 -AdminToken "your_fixed_token_here"
#   .\udm_doctor.ps1 -KernelUrl "http://localhost:8000"

param(
  [string]$KernelUrl = "http://localhost:8000",
  [int]$Scenarios = 240,
  [int]$Seed = 42,
  [string]$BlockSpec = "SAFE:3,RISKY:1",
  [string]$AdminToken = "",
  [int]$HealthTimeoutSec = 40,
  [int]$RequestTimeoutSec = 600
)

$ErrorActionPreference = "Stop"

function Fail($msg){ Write-Host "[ERR] $msg" -ForegroundColor Red; exit 1 }
function Info($msg){ Write-Host "[i] $msg" -ForegroundColor Cyan }
function Ok($msg){ Write-Host "[OK] $msg" -ForegroundColor Green }
function Warn($msg){ Write-Host "[! ] $msg" -ForegroundColor Yellow }

# --- Sanity: repo structure ---
if (-not (Test-Path ".\UDM_OS\app\kernel_app.py")) {
  Fail "Not in repo root. UDM_OS/app/kernel_app.py not found."
}

# --- Helpers ---
function Invoke-Json {
  param([string]$Method,[string]$Url,[object]$Body=$null,[int]$TimeoutSec=60)
  $headers = @{ "Content-Type" = "application/json" }
  $opts = @{ Method=$Method; Uri=$Url; Headers=$headers; TimeoutSec=$TimeoutSec }
  if ($null -ne $Body) { $opts.Body = ($Body | ConvertTo-Json -Depth 10 -Compress) }
  try {
    $resp = Invoke-RestMethod @opts
    return $resp
  } catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $status = [int]$_.Exception.Response.StatusCode
      $txt = ""
      try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $txt = $sr.ReadToEnd() } catch {}
      Fail ("HTTP {0} {1}" -f $status, $txt)
    }
    Fail $_.Exception.Message
  }
}

function Kill-Port8000 {
  $list = (netstat -ano | findstr :8000) 2>$null
  if (-not $list) { return }
  $pids = @()
  foreach ($line in $list) {
    if ($line -match '\s+(\d+)\s*$') { $pids += [int]$matches[1] }
  }
  $pids = $pids | Select-Object -Unique
  foreach ($procId in $pids) {
    try {
      Stop-Process -Id $procId -Force -ErrorAction Stop
      Warn ("Killed process PID {0} using :8000" -f $procId)
    } catch {
      Warn ("Could not kill PID {0}: {1}" -f $procId, $_.Exception.Message)
    }
  }
}

function Generate-Token {
  if (Test-Path ".\tools\gen_secret.ps1") {
    return & .\tools\gen_secret.ps1
  }
  if (Test-Path ".\UDM_OS\tools\gen_secret.ps1") {
    return & .\UDM_OS\tools\gen_secret.ps1
  }
  # Fallback 32 bytes -> 64 hex
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Start-Kernel {
  param([string]$Token)
  if (-not (Test-Path ".\run_kernel.ps1")) { Fail "run_kernel.ps1 not found." }
  $env:UDM_ADMIN_TOKEN = $Token
  if (-not $env:UDM_API_VERSION) { $env:UDM_API_VERSION = "1.0.0" }
  Info "Starting kernel with admin token..."
  try {
    & .\run_kernel.ps1 -Restart 2>$null | Out-Null
  } catch {
    & .\run_kernel.ps1 | Out-Null
  }
  Start-Sleep -Seconds 1
}

function Wait-Health {
  param([int]$TimeoutSec)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    try {
      $h = Invoke-Json -Method GET -Url ($KernelUrl.TrimEnd('/') + "/health") -TimeoutSec 5
      if ($h.ok -eq $true) { return $h }
    } catch { Start-Sleep -Milliseconds 400 }
  } while ((Get-Date) -lt $deadline)
  Fail "Kernel health check timed out after $TimeoutSec s."
}

function Get-LastAIGReport {
  $files = Get-ChildItem "UDM_OS\.udm\reports\udm_ai_gov_report_*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
  if (-not $files) { return $null }
  $p = $files[0].FullName
  $json = Get-Content $p -Raw | ConvertFrom-Json
  return @{ Path=$p; Json=$json }
}

function Parse-Rates {
  param([object]$Case)
  $safe=$null; $risky=$null
  foreach ($d in $Case.details) {
    if ($d -match 'safe:\s+\d+/\d+.*rate=([0-9\.]+)')  { $safe  = [double]$matches[1] }
    if ($d -match 'risky:\s+\d+/\d+.*rate=([0-9\.]+)') { $risky = [double]$matches[1] }
  }
  return @{ safe=$safe; risky=$risky }
}

function Run-BlockTest {
  param([string]$Token,[int]$Scenarios,[int]$Seed,[string]$BlockSpec)
  $body = @{
    admin_token       = $Token
    AIG_SCENARIOS     = $Scenarios
    AIG_RISKY_SHARE   = 0.5
    AIG_MAX_RISKY_OPEN= 0.02
    AIG_MIN_SAFE_OPEN = 0.60
    AIG_SEED          = $Seed
    AIG_EXPLAIN       = 1
    AIG_BLOCK_SPEC    = $BlockSpec
    AIG_BLOCK_ROUNDS  = 0
  }
  $urlBlocks = ($KernelUrl.TrimEnd('/') + "/tests/ai_gov/run_blocks")
  $urlPlain  = ($KernelUrl.TrimEnd('/') + "/tests/ai_gov/run")
  try {
    Info "Running AI Governance Hard Test (block-scheduled)..."
    Invoke-Json -Method POST -Url $urlBlocks -Body $body -TimeoutSec $RequestTimeoutSec | Out-Null
  } catch {
    Warn "run_blocks endpoint unavailable; falling back to random test."
    $body.Remove("AIG_BLOCK_SPEC") | Out-Null
    $body.Remove("AIG_BLOCK_ROUNDS") | Out-Null
    Invoke-Json -Method POST -Url $urlPlain -Body $body -TimeoutSec $RequestTimeoutSec | Out-Null
  }
  Start-Sleep -Milliseconds 200
  $rep = Get-LastAIGReport
  if (-not $rep) { Fail "No AI gov report found after test run." }
  $sum  = $rep.Json.summary
  $case = ($rep.Json.cases | Where-Object { $_.name -eq "AIG.hardtest" })
  $rates = Parse-Rates -Case $case
  return @{ Ok=($sum.pass -ge 1); Path=$rep.Path; Safe=$rates.safe; Risky=$rates.risky }
}

# --- 1) Kill any stuck kernels on :8000 ---
Info "Checking for stuck processes on :8000..."
Kill-Port8000

# --- 2) Prepare token ---
if ([string]::IsNullOrWhiteSpace($AdminToken)) {
  $AdminToken = Generate-Token
  Warn ("Generated new admin token:")
  Write-Host $AdminToken -ForegroundColor Green
} else {
  Info "Using provided admin token."
}
$env:UDM_ADMIN_TOKEN = $AdminToken

# --- 3) Start kernel (fresh) & wait for health ---
Start-Kernel -Token $AdminToken
$health = Wait-Health -TimeoutSec $HealthTimeoutSec
Ok ("Kernel up. version={0} hys_depth={1}" -f $health.version, $health.hys_depth)

# --- 4) Quick connectivity sanity ---
try {
  $ps = Invoke-Json -Method GET -Url ($KernelUrl.TrimEnd('/') + "/public/state") -TimeoutSec 8
  Ok ("Public state OK: state={0}" -f $ps.state)
} catch {
  Warn "Public state check failed (continuing): $($_.Exception.Message)"
}

# --- 5) Run the AI gov hard test (block-scheduled by default) ---
$res = Run-BlockTest -Token $AdminToken -Scenarios $Scenarios -Seed $Seed -BlockSpec $BlockSpec

Write-Host ""
Write-Host ("Report: {0}" -f $res.Path)
if ($res.Ok) {
  Ok ("PASS  safe={0:P1}  risky={1:P1}" -f $res.Safe, $res.Risky)
} else {
  Write-Host ("FAIL  safe={0:P1}  risky={1:P1}" -f $res.Safe, $res.Risky) -ForegroundColor Red
  Write-Host "Tip: keep Default ACTIVE, use block spec (SAFE:3,RISKY:1), or increase scenarios to 360."
}

Write-Host ""
Write-Host "Paste this token into your Dashboard 'admin token' field:" -ForegroundColor Yellow
Write-Host $AdminToken -ForegroundColor Green
