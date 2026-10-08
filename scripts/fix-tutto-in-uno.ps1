# fix-tutto-in-uno.ps1 - Risolve i problemi di estrazione in un sol comando
# Copia il file parser corretto dentro il container, riavvia, pulisce le bozze errate.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "[1/5] Copio il parser aggiornato nel container backend..." -ForegroundColor Cyan
docker cp backend/app/services/extraction.py vitasync-backend-test:/app/app/services/extraction.py

Write-Host "[2/5] Verifico che il parser sia sintatticamente valido..." -ForegroundColor Cyan
docker exec vitasync-backend-test python -c "import ast; ast.parse(open('/app/app/services/extraction.py').read()); print('OK sintassi')"

Write-Host "[3/5] Riavvio il backend di test..." -ForegroundColor Cyan
docker compose -f docker-compose.test-ocr.yml restart backend | Out-Null

Write-Host "[4/5] Pulisco le bozze errate (i valori gia' CONFERMATI da te non vengono toccati)..." -ForegroundColor Cyan
docker exec vitasync-pg-test psql -U vitasync -d vitasync -c "DELETE FROM lab_tests WHERE confirmed_by_user = false;"

Write-Host "[5/5] Controllo che il backend sia attivo..." -ForegroundColor Cyan
Start-Sleep -Seconds 8
Invoke-RestMethod http://localhost:8001/health | ConvertTo-Json -Depth 3

Write-Host "FATTO! Adesso apri http://localhost:3002 , vai su Documenti, apri il referto e premi 'Estrai'." -ForegroundColor Green
Write-Host "Non dovresti piu' vedere indirizzi/telefoni tra i valori ne' errori 'Failed to fetch'."
