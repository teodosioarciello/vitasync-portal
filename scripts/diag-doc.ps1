# diag-doc.ps1 - Diagnostica un documento senza bisogno di credenziali
# Uso: .\scripts\diag-doc.ps1  (senza parametro analizza l'ultimo documento caricato)
param([string]$Id = "")
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Id)) {
    Write-Host "Nessun ID fornito: uso l'ultimo documento nel database." -ForegroundColor Yellow
    $Id = (docker exec vitasync-pg-test psql -U vitasync -d vitasync -t -A -c "SELECT id FROM documents ORDER BY created_at DESC LIMIT 1;").Trim()
}
Write-Host "Documento: $Id" -ForegroundColor Cyan

Write-Host "`n--- METADATI E FILE ---" -ForegroundColor Cyan
docker exec vitasync-backend-test python -c @"
from app.db.session import SessionLocal
from app.db.models import Document
db = SessionLocal(); d = db.get(Document, '$Id')
print('METADATA:', d.metadata_json)
print('FILE:', d.storage_key)
"@

Write-Host "`n--- TESTO ESTRAITO (primi 1500 caratteri) ---" -ForegroundColor Cyan
docker exec vitasync-backend-test python -c @"
from app.services.extraction import resolve_document_path
from app.db.session import SessionLocal
from app.db.models import Document
import fitz
db = SessionLocal(); d = db.get(Document, '$Id'); p = resolve_document_path(d)
doc = fitz.open(str(p)); t = chr(10).join(pg.get_text() for pg in doc)
print(t[:1500] if t.strip() else '(nessun testo embedded: OCR attivo)')
"@

Write-Host "`n--- VALORI BOZZA ATTUALI ---" -ForegroundColor Cyan
docker exec vitasync-pg-test psql -U vitasync -d vitasync -c "SELECT test_name_original, value_numeric, unit FROM lab_tests WHERE document_id='$Id' ORDER BY created_at DESC LIMIT 20;"
