# apply-fix.ps1 - Aggiorna il parser e riavvia il backend di test
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "[1/4] Applico la fix al parser (filtro righe spazzatura + valori implausibili)..." -ForegroundColor Cyan
docker exec vitasync-backend-test python /app/scripts/apply-junk-filter.py

Write-Host "[2/4] Riavvio il backend di test..." -ForegroundColor Cyan
docker compose -f docker-compose.test-ocr.yml restart backend

Write-Host "[3/4] Pulisco le bozze errate gia' create (i dati confermati da te NON vengono toccati)..." -ForegroundColor Cyan
docker exec vitasync-pg-test psql -U vitasync -d vitasync -c "DELETE FROM lab_tests WHERE confirmed_by_user = false;"

Write-Host "[4/4] Attendo il riavvio e verifico l'health check..." -ForegroundColor Cyan
Start-Sleep -Seconds 8
Invoke-RestMethod http://localhost:8001/health | ConvertTo-Json -Depth 3

Write-Host "FATTO. Ora ricarica il documento dalla pagina Documenti e premi 'Estrai'." -ForegroundColor Green
