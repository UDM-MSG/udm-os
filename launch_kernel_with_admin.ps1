# launch_kernel_with_admin.ps1
# Generates an admin token, prints it clearly, exports it, and (re)starts kernel.
$ErrorActionPreference = "Stop"
$token = & .\tools\gen_secret.ps1
Write-Host ("UDM_ADMIN_TOKEN = {0}" -f $token) -ForegroundColor Cyan
$env:UDM_ADMIN_TOKEN = $token
if (-not $env:UDM_API_VERSION) { $env:UDM_API_VERSION = "1.0.0" }
.\run_kernel.ps1 -Restart
Write-Host "Paste this token into the Dashboard 'admin token' field:" -ForegroundColor Yellow
Write-Host $token -ForegroundColor Green
