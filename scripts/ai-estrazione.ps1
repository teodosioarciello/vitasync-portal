# ai-estrazione.ps1 - Avvia lo stack di test con estrazione AI locale (Ollama) e lo configura.
# Uso:  powershell -ExecutionPolicy Bypass -File .\scripts\ai-estrazione.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "[1/6] Controllo Docker Desktop..." -ForegroundColor Cyan
docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE: Docker Desktop non e' in esecuzione. Aprilo e riprova." -ForegroundColor Red; exit 1 }
Write-Host "      Docker OK" -ForegroundColor Green

Write-Host "[2/6] Creo il file .env per lo stack di test (AI estrazione ON, tutto locale)..." -ForegroundColor Cyan
@"
OCR_BACKEND=hybrid
OCR_OLLAMA_BASE_URL=http://ollama:11434
OCR_OLLAMA_MODEL=qwen2.5vl:3b
OCR_OLLAMA_TIMEOUT_SECONDS=300
OCR_FALLBACK_TO_TESSERACT=true
LAB_EXTRACT_ENABLED=true
LAB_EXTRACT_MODEL=
LAB_EXTRACT_MIN_ITEMS=2
"@ | Set-Content -Path ".env.test-ocr" -Encoding UTF8
Write-Host "      .env.test-ocr creato" -ForegroundColor Green

Write-Host "[3/6] Avvio i container (postgres, redis, ollama, backend, frontend)..." -ForegroundColor Cyan
docker compose -f docker-compose.test-ocr.yml --env-file .env.test-ocr up -d --build

Write-Host "[4/6] Attendo che il backend risponda (max 90s)..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 3
    try {
        $h = Invoke-RestMethod http://localhost:8001/health -TimeoutSec 5
        $ok = $true; break
    } catch {}
}
if (-not $ok) { Write-Host "ERRORE: backend non raggiunge lo stato healthy. Log:" -ForegroundColor Red; docker logs vitasync-backend-test --tail 40; exit 1 }
$h | ConvertTo-Json -Depth 4

Write-Host "[5/6] Scarico il modello AI qwen2.5vl:3b (~4 GB, solo la prima volta - puo' impiegare anche 30+ minuti)..." -ForegroundColor Cyan
docker exec vitasync-ollama-test ollama list | Select-String "qwen2.5vl" -Quiet | ForEach-Object {
    if ($_ -eq "True") { Write-Host "      Modello gia' presente, salto il download." -ForegroundColor Green }
    else { docker exec vitasync-ollama-test ollama pull qwen2.5vl:3b }
}

Write-Host "[6/6] Pulisco le vecchie bozze errate (i valori CONFERMATI da te restano)..." -ForegroundColor Cyan
docker exec vitasync-pg-test psql -U vitasync -d vitasync -c "DELETE FROM lab_tests WHERE confirmed_by_user = false;"

Write-Host ""
Write-Host "FATTO! Ora:" -ForegroundColor Green
Write-Host "  1. Apri  http://localhost:3002  e fai login"
Write-Host "  2. Vai su Documenti -> apri un referto -> premi 'Estrai'"
Write-Host "     (la prima estrazione AI puo' richiedere 1-3 minuti: il modello viene caricato in RAM)"
Write-Host "  3. Nella pagina Review vedrai SOLO i veri esami interpretati dall'AI locale, da confermare."
Write-Host "Per vedere in diretta cosa fa l'AI:  docker logs -f vitasync-backend-test"
