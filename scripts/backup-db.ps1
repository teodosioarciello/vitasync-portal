#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$BackupRoot = "D:\RD\VitaSync\backups\db"
)

$ErrorActionPreference = "Stop"

function Invoke-DockerCompose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ComposeArgs
    )

    Write-Host ("docker compose " + ($ComposeArgs -join " ")) -ForegroundColor DarkGray
    & docker compose @ComposeArgs

    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($ComposeArgs -join ' ')"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath "docker-compose.yml")) {
    throw "docker-compose.yml non trovato in $repoRoot. Esegui lo script dalla root del repo o da scripts\backup-db.ps1."
}

if (-not (Test-Path -LiteralPath $BackupRoot)) {
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $BackupRoot "vitasync-db-$stamp.dump"
$containerTmp = "/tmp/vitasync-backup-$stamp.dump"

Write-Host "Backup DB PostgreSQL in corso..." -ForegroundColor Cyan
Write-Host "Output: $out" -ForegroundColor Green

Invoke-DockerCompose @("exec", "-T", "postgres", "sh", "-lc", "pg_dump -U vitasync -d vitasync -Fc -f '$containerTmp'")
Invoke-DockerCompose @("exec", "-T", "postgres", "sh", "-lc", "pg_restore --list '$containerTmp' > /dev/null")
Invoke-DockerCompose @("cp", "postgres:$containerTmp", $out)
Invoke-DockerCompose @("exec", "-T", "postgres", "sh", "-lc", "rm -f '$containerTmp'")

if (-not (Test-Path -LiteralPath $out)) {
    throw "Dump non creato: $out"
}

$item = Get-Item -LiteralPath $out
if ($item.Length -le 0) {
    throw "Dump vuoto: $out"
}

Write-Host "Backup completato." -ForegroundColor Green
Write-Host ("File: {0}" -f $item.FullName) -ForegroundColor Cyan
Write-Host ("Dimensione: {0} bytes" -f $item.Length) -ForegroundColor Cyan