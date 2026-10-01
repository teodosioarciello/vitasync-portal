param(
    [string]$OutDir = "D:\RD\VitaSync\backups\data"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo

try {
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $zip   = Join-Path $OutDir ("vitasync-data-" + $stamp + ".zip")
    $temp  = Join-Path $env:TEMP ("vitasync-data-" + [Guid]::NewGuid().ToString())

    New-Item -ItemType Directory -Force -Path $temp | Out-Null

    $dataDir = Join-Path $repo "data"

    if (Test-Path $dataDir) {
        robocopy $dataDir $temp /E /NFL /NDL /NJH /NJS /NP
    }

    if ((Get-ChildItem $temp -Recurse -File).Count -eq 0) {
        Set-Content -Path (Join-Path $temp "README.txt") -Value "data/ vuoto al momento del backup."
        Write-Host "ATTENZIONE: data/ vuoto; zip conterrà solo placeholder." -ForegroundColor Yellow
    }

    if (Test-Path $zip) { Remove-Item -Force $zip }

    Compress-Archive -Path (Join-Path $temp '*') -DestinationPath $zip -Force
    Remove-Item -Recurse -Force $temp

    Write-Host "Backup data creato:" -ForegroundColor Green
    Get-Item $zip | Select-Object FullName, Length, LastWriteTime | Format-List
}
finally {
    Pop-Location
}