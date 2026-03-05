# Start the UDM kernel (run.ps1 lives in UDM_OS). Skips if port already in use.
# Use: .\run_kernel.ps1          - start only if port free
#      .\run_kernel.ps1 -Restart - stop process on port first, then start
param([switch]$Restart)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = if ($env:UDM_PORT) { [int]$env:UDM_PORT } else { 8000 }
$inUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    if ($Restart) {
        $conn = $inUse | Select-Object -First 1
        $procId = $conn.OwningProcess
        if ($procId) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $maxWait = 15
            for ($i = 0; $i -lt $maxWait; $i++) {
                Start-Sleep -Seconds 1
                $stillInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
                if (-not $stillInUse) { break }
            }
            if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
                Write-Host "Port $Port still in use after ${maxWait}s. Try closing the app using the port, then run again."
                exit 1
            }
            Write-Host "Stopped previous kernel (PID $procId). Starting fresh..."
        } else {
            Write-Host "Port $Port in use but could not get process ID. Close the app using the port and run again."
            exit 1
        }
    } else {
        Write-Host "Kernel already running at http://localhost:$Port - no second instance started."
        Write-Host ""
        Write-Host "To load latest code (e.g. /simulate/list, Domain Sims), RESTART the kernel:"
        Write-Host "  .\run_kernel.ps1 -Restart"
        Write-Host ""
        exit 0
    }
}
Set-Location (Join-Path $ScriptDir "UDM_OS")
& .\run.ps1
