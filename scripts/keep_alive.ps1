<#
.SYNOPSIS
    Render Keep-Alive Pinger for OatEasy AI
.DESCRIPTION
    Pings the Render endpoint periodically (default every 12 minutes)
    to prevent Render's free tier from entering sleep/idle state.
#>

param (
    [string]$Url = "https://oateasy-ai.onrender.com/health",
    [int]$IntervalMinutes = 12
)

$IntervalSeconds = $IntervalMinutes * 60

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " OatEasy Render Keep-Alive Script" -ForegroundColor Green
Write-Host " Target URL : $Url"
Write-Host " Frequency  : Every $IntervalMinutes minutes ($IntervalSeconds seconds)"
Write-Host " Press Ctrl+C to stop"
Write-Host "============================================================" -ForegroundColor Cyan

while ($true) {
    $time = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 30
        $stopwatch.Stop()
        Write-Host "[$time] [SUCCESS] Pinged $Url in $($stopwatch.ElapsedMilliseconds)ms - Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Green
    }
    catch {
        Write-Host "[$time] [ERROR] Failed to ping $Url - $_" -ForegroundColor Red
    }
    Start-Sleep -Seconds $IntervalSeconds
}
