param(
    [string]$DumpPath,
    [switch]$Keep
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo

$drillDb = "vitasync_drill"
$ok = $true

try {
    # 1. Selezione dump (default: ultimo backup disponibile)
    if (-not $DumpPath) {
        $latest = Get-ChildItem "D:\RD\VitaSync\backups\db\vitasync-db-*.dump" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if (-not $latest) {
            throw "Nessun dump trovato in D:\RD\VitaSync\backups\db. Esegui prima backup-db.ps1."
        }

        $DumpPath = $latest.FullName
    }

    if (-not (Test-Path -LiteralPath $DumpPath)) { throw "Dump non trovato: $DumpPath" }

    $len = (Get-Item -LiteralPath $DumpPath).Length
    if ($len -le 0) { throw "Dump vuoto: $DumpPath" }

    Write-Host "Dump selezionato: $DumpPath ($len bytes)" -ForegroundColor Cyan

    # 2. Rilevamento formato: custom pg_dump (PGDMP) oppure plain SQL
    $bytes = [System.IO.File]::ReadAllBytes($DumpPath)
    $head = ""
    $n = [Math]::Min(5, $bytes.Length)
    for ($i = 0; $i -lt $n; $i++) { $head += [char]$bytes[$i] }

    $isCustom = ($head -eq "PGDMP")

    if ($isCustom) {
        Write-Host "Formato rilevato: custom (pg_restore)." -ForegroundColor Cyan
    } else {
        Write-Host "Formato rilevato: plain SQL (psql)." -ForegroundColor Cyan
    }

    # 3. Database drill ISOLATO: mai toccare il DB production vitasync
    Write-Host "Creazione database isolato $drillDb..." -ForegroundColor Cyan
    docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $drillDb;"
    docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $drillDb;"

    # 4. Copia del dump nel container e restore nel DB drill
    docker compose cp "$DumpPath" postgres:/tmp/vitasync-drill.dump

    if ($isCustom) {
        docker compose exec -T postgres pg_restore -U vitasync -d $drillDb --no-owner --no-privileges /tmp/vitasync-drill.dump
    } else {
        docker compose exec -T postgres psql -U vitasync -d $drillDb -v ON_ERROR_STOP=1 -f /tmp/vitasync-drill.dump
    }

    $restoreExit = $LASTEXITCODE

    if ($restoreExit -ne 0) {
        Write-Host "RESTORE FALLITO con exit code $restoreExit." -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Restore completato con exit code 0." -ForegroundColor Green
    }

    # 5. Verifica tabelle attese e confronto conteggi prod vs drill
    $tables = @(
        "users", "families", "patients", "documents", "lab_tests",
        "medicines", "therapies", "reminders", "notification_logs", "audit_logs"
    )

    $presentRaw = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select string_agg(table_name, ',' order by table_name) from information_schema.tables where table_schema='public';"
    $present = @()
    if ($presentRaw) { $present = $presentRaw -split ',' }

    $missing = @()
    foreach ($t in $tables) {
        if ($present -notcontains $t) { $missing += $t }
    }

    if ($missing.Count -gt 0) {
        Write-Host "TABELLE MANCANTI NEL DRILL: $($missing -join ', ')" -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Tutte le tabelle attese sono presenti nel drill." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Confronto conteggi (prod vs drill):" -ForegroundColor Cyan

    foreach ($t in $tables) {
        if ($missing -contains $t) {
            "{0,-20} prod=?      drill=MANCANTE" -f $t
            continue
        }

        $cProd  = docker compose exec -T postgres psql -U vitasync -d vitasync     -tAc "select count(*) from $t;"
        $cDrill = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select count(*) from $t;"
        "{0,-20} prod={1,7} drill={2,7}" -f $t, $cProd, $cDrill
    }

    $usersDrill = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select count(*) from users;"
    if ([int]$usersDrill -lt 1) {
        Write-Host "FAIL: nessun utente nel DB ripristinato." -ForegroundColor Red
        $ok = $false
    }

    # 6. Cleanup (salta solo con -Keep, per ispezione manuale)
    if (-not $Keep) {
        docker compose exec -T postgres rm -f /tmp/vitasync-drill.dump
        docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $drillDb;"
        Write-Host "Cleanup completato: dump temporaneo e $drillDb rimossi." -ForegroundColor Green
    } else {
        Write-Host "Keep attivo: /tmp/vitasync-drill.dump e $drillDb lasciati per ispezione." -ForegroundColor Yellow
    }

    Write-Host ""
    if ($ok) {
        Write-Host "DISASTER RECOVERY DRILL: PASS" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "DISASTER RECOVERY DRILL: FAIL" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}