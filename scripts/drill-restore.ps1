param(
    [string]$DumpPath,
    [switch]$Keep
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo

$drillDb = "vitasync_drill"
$ok = $true
$dumpSelected = $false

try {
    if (-not $DumpPath) {
        $latest = Get-ChildItem "D:\RD\VitaSync\backups\db\vitasync-db-*.dump" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if (-not $latest) {
            throw "Nessun dump trovato in D:\RD\VitaSync\backups\db. Esegui prima backup-db.ps1."
        }

        $DumpPath = $latest.FullName
    }

    if (-not (Test-Path -LiteralPath $DumpPath)) {
        throw "Dump non trovato: $DumpPath"
    }

    $len = (Get-Item -LiteralPath $DumpPath).Length
    if ($len -le 0) {
        throw "Dump vuoto: $DumpPath"
    }

    Write-Host "Dump selezionato: $DumpPath ($len bytes)" -ForegroundColor Cyan
    $dumpSelected = $true

    $bytes = [System.IO.File]::ReadAllBytes($DumpPath)
    $head = ""
    $n = [Math]::Min(5, $bytes.Length)
    for ($i = 0; $i -lt $n; $i++) {
        $head += [char]$bytes[$i]
    }

    $isCustom = ($head -eq "PGDMP")

    if ($isCustom) {
        Write-Host "Formato rilevato: custom (pg_restore)." -ForegroundColor Cyan
    } else {
        Write-Host "Formato rilevato: plain SQL (psql)." -ForegroundColor Cyan
    }

    Write-Host "Creazione database isolato $drillDb..." -ForegroundColor Cyan

    docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $drillDb;"
    docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $drillDb;"

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

    $tables = @(
        "users",
        "families",
        "patients",
        "documents",
        "lab_tests",
        "medicines",
        "therapies",
        "reminders",
        "notification_logs",
        "audit_logs",
        "user_settings"
    )

    $presentRaw = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select string_agg(table_name, ',' order by table_name) from information_schema.tables where table_schema='public';"
    $present = @()

    if ($presentRaw) {
        $present = ($presentRaw.Trim() -split ',')
    }

    $missing = @()

    foreach ($t in $tables) {
        if ($present -notcontains $t) {
            $missing += $t
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "TABELLE MANCANTI NEL DRILL: $($missing -join ', ')" -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Tutte le tabelle attese sono presenti nel drill." -ForegroundColor Green
    }

    # ---------------------------------------------------------------------
    # Verifica struttura user_settings post Step 4E
    # ---------------------------------------------------------------------

    $colsRaw = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select string_agg(column_name, ',' order by column_name) from information_schema.columns where table_schema='public' and table_name='user_settings';"
    $cols = @()

    if ($colsRaw) {
        $cols = ($colsRaw.Trim() -split ',')
    }

    $requiredCore = @(
        "user_id",
        "notification_channel",
        "notifications_enabled",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_from",
        "smtp_use_tls"
    )

    $missingCore = @()

    foreach ($c in $requiredCore) {
        if ($cols -notcontains $c) {
            $missingCore += $c
        }
    }

    if ($missingCore.Count -gt 0) {
        Write-Host "COLONNE USER_SETTINGS MANCANTI: $($missingCore -join ', ')" -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Colonne core user_settings presenti." -ForegroundColor Green
    }

    $passwordCols = @($cols | Where-Object { $_ -match 'password' })

    if ($passwordCols.Count -eq 0) {
        Write-Host "Nessuna colonna password SMTP trovata in user_settings." -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Colonna/e password SMTP presenti: $($passwordCols -join ', ')" -ForegroundColor Green
    }

    # ---------------------------------------------------------------------
    # Verifica integrità FK user_settings -> users
    # ---------------------------------------------------------------------

    $orphansRaw = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select count(*) from user_settings us left join users u on u.id = us.user_id where u.id is null;"
    $orphans = 0

    if ($orphansRaw) {
        $orphans = [int]$orphansRaw.Trim()
    }

    if ($orphans -gt 0) {
        Write-Host "FAIL: righe user_settings orfane rispetto a users: $orphans" -ForegroundColor Red
        $ok = $false
    } else {
        Write-Host "Nessuna riga user_settings orfana." -ForegroundColor Green
    }

    # ---------------------------------------------------------------------
    # Confronto conteggi production vs drill
    # ---------------------------------------------------------------------

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

    $usersDrillRaw = docker compose exec -T postgres psql -U vitasync -d $drillDb -tAc "select count(*) from users;"
    $usersDrill = 0

    if ($usersDrillRaw) {
        $usersDrill = [int]$usersDrillRaw.Trim()
    }

    if ($usersDrill -lt 1) {
        Write-Host "FAIL: nessun utente nel DB ripristinato." -ForegroundColor Red
        $ok = $false
    }

    # ---------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------

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
catch {
    Write-Host "ERRORE DRILL: $($_.Exception.Message)" -ForegroundColor Red

    if (-not $Keep -and $dumpSelected) {
        try {
            docker compose exec -T postgres rm -f /tmp/vitasync-drill.dump 2>$null | Out-Null
            docker compose exec -T postgres psql -U vitasync -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $drillDb;" 2>$null | Out-Null
            Write-Host "Cleanup di emergenza completato." -ForegroundColor Yellow
        } catch {
            Write-Host "Cleanup di emergenza non riuscito. Controlla manualmente il DB $drillDb." -ForegroundColor Red
        }
    }

    exit 1
}
finally {
    Pop-Location
}