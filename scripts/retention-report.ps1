param([int]$Days = 30)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo

try {
    Write-Host "VitaSync retention report sicuro" -ForegroundColor Cyan
    Write-Host "Retention giorni: $Days" -ForegroundColor Cyan
    Write-Host "Nessun documento verra' eliminato." -ForegroundColor Yellow
    Write-Host ""

    docker compose run --rm backend python scripts/report_retention_trash.py --days $Days
}
finally {
    Pop-Location
}