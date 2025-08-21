param([string]$Key)
$ErrorActionPreference="Stop"
if (-not $Key) { Write-Host "Usage: ./scripts/smoke.ps1 -Key <x-api-key>"; exit 1 }
Invoke-WebRequest "http://127.0.0.1:5000/speak?text=Hello%20Naija" -Headers @{ "x-api-key"=$Key } -OutFile "$env:TEMP\odiadev_smoke.wav"
Start-Process "$env:TEMP\odiadev_smoke.wav"
