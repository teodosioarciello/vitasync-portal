# scripts/backup_full.ps1
# Backup completo VitaSync: DB Postgres + storage documenti + .env + stato git.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\backup_full.ps1
param([string]$OutRoot = "backups")

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $dest = Join-Path (Join-Path $root $OutRoot) $ts
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Write-Host "=== BACKUP VITASYNC $ts ===" -ForegroundColor Cyan
    Write-Host "Destinazione: $dest"

    # --- 1. Stato git ---
    $gitHead = (git rev-parse --short HEAD) 2>$null
    $gitBranch = (git rev-parse --abbrev-ref HEAD) 2>$null
    $gitDirty = (git status --porcelain) 2>$null
    Write-Host "Git: $gitBranch @ $gitHead"

    # --- 2. Dump database (custom + plain) ---
    Write-Host "`n-- Dump DB --" -ForegroundColor Yellow
    docker compose exec -T postgres sh -c "pg_dump -U vitasync -d vitasync -Fc -f /tmp/vitasync.dump"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump custom fallito" }
    docker compose cp postgres:/tmp/vitasync.dump (Join-Path $dest "vitasync.dump")
    if ($LASTEXITCODE -ne 0) { throw "cp dump custom fallito" }

    docker compose exec -T postgres sh -c "pg_dump -U vitasync -d vitasync -Fp -f /tmp/vitasync.sql"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump plain fallito" }
    docker compose cp postgres:/tmp/vitasync.sql (Join-Path $dest "vitasync.sql")
    if ($LASTEXITCODE -ne 0) { throw "cp dump plain fallito" }

    docker compose exec -T postgres sh -c "rm -f /tmp/vitasync.dump /tmp/vitasync.sql"
    Write-Host "Dump DB OK (vitasync.dump + vitasync.sql)"

    # --- 3. Storage documenti ---
    Write-Host "`n-- Storage documenti --" -ForegroundColor Yellow
    $docDest = Join-Path $dest "documents"
    New-Item -ItemType Directory -Force -Path $docDest | Out-Null
    $localData = Join-Path $root "data\documents"
    $storageSource = "none"
    if (Test-Path $localData) {
        Copy-Item -Path (Join-Path $localData "*") -Destination $docDest -Recurse -Force -ErrorAction SilentlyContinue
        $storageSource = "local-bind-mount"
        Write-Host "Copiato da bind mount locale: $localData"
    } else {
        docker compose cp backend:/app/data/documents $docDest
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ATTENZIONE: nessuno storage locale ne' nel container." -ForegroundColor Red
        } else {
            $storageSource = "container-backend"
            Write-Host "Copiato dal container backend:/app/data/documents"
        }
    }

    # --- 4. .env (SENSIBILE) ---
    Write-Host "`n-- .env --" -ForegroundColor Yellow
    $envf = Join-Path $root ".env"
    if (Test-Path $envf) {
        Copy-Item $envf (Join-Path $dest ".env")
        Write-Host "Copiato .env (CONTIENE SEGRETI: non condividere)."
    } else {
        Write-Host "Nessun .env trovato."
    }

    # --- 5. Manifest + checksum ---
    Write-Host "`n-- Manifest --" -ForegroundColor Yellow
    $manifest = Join-Path $dest "MANIFEST.txt"
    $lines = @()
    $lines += "VitaSync backup $ts"
    $lines += "Generated: $(Get-Date -Format o)"
    $lines += "Git branch: $gitBranch"
    $lines += "Git HEAD: $gitHead"
    $lines += "Git dirty at backup time:"
    if ($gitDirty) { $lines += $gitDirty } else { $lines += "  (clean)" }
    $lines += "Storage source: $storageSource"
    $lines += ""
    $lines += "FILES:"
    Get-ChildItem -Path $dest -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($dest.Length + 1)
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
        $lines += ("  {0,-40} {1,12} bytes  sha256={2}" -f $rel, $_.Length, $sha)
    }
    $lines += ""
    $lines += "AVVISO: questo backup contiene .env con segreti reali."
    $lines += "Non condividerlo, non committarlo, cancellarlo dopo l'uso."
    [System.IO.File]::WriteAllLines($manifest, $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Manifest scritto."

    # --- 6. Zip ---
    $zip = "$dest.zip"
    Compress-Archive -Path $dest -DestinationPath $zip -Force
    Write-Host "Zip creato: $zip"

    Write-Host "`n=== BACKUP COMPLETATO ===" -ForegroundColor Green
    Write-Host "Cartella: $dest"
    Write-Host "Zip:      $zip"
} finally {
    Pop-Location
}