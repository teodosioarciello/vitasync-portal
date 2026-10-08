# fix-tutto-in-uno.ps1 - Risolve i problemi di estrazione in un sol comando
# (nessun file da scaricare, nessuna patch da applicare)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "[1/5] Aggiorno il parser nel container backend (filtro righe spazzatura + valori implausibili)..." -ForegroundColor Cyan
docker exec vitasync-backend-test python -c @'
import re
p = "/app/app/services/extraction.py"
src = open(p, encoding="utf-8").read()
if "_is_junk_line" not in src:
    helpers = """

JUNK_LINE_WORDS = {
    "pagina", "pag.", "tel.", "fax", "email", "pec", "www", "http", "referto",
    "sottoscritto", "firmato", "firma", "digitale", "legge", "d.lgs", "decreto",
    "allegato", "note", "metodo", "data prelievo", "data consegna", "medico",
    "direttore", "laboratorio", "indirizzo", "via ", "viale", "corso", "piazza",
    "aut.", "min.", "autorizzazione", "protocollo", "codice fiscale", "partita iva",
}
JUNK_LEADING_WORDS = {"pag", "tel", "fax", "www", "referto", "firmato", "spedito", "emesso", "trasmesso"}

def _is_junk_line(line):
    low = line.strip().lower()
    if not low:
        return True
    words = set(re.findall(r"[a-z\u00e0-\u00ff][a-z\u00e0-\u00ff\\.\\-]{2,}", low))
    if words & JUNK_LINE_WORDS:
        return True
    first = low.split()[0].rstrip(".,:") if low.split() else ""
    if first in JUNK_LEADING_WORDS:
        return True
    toks = [t for t in re.split(r"\\s+", low) if t]
    letters = sum(c.isalpha() for t in toks for c in t)
    if len(toks) >= 6 and letters < 18:
        return True
    return False

def _value_is_plausible(num):
    try:
        return num is not None and abs(float(num)) <= 1_000_000
    except Exception:
        return False
"""
    m = re.search(r"\ndef parse_lab_lines", src)
    if not m:
        raise SystemExit("ERRORE: funzione parse_lab_lines non trovata")
    src = src[:m.start()] + helpers + src[m.start():]
    src = src.replace("for raw in text.splitlines():\n        line = raw.strip()",
                      "for raw in text.splitlines():\n        line = raw.strip()\n        if _is_junk_line(line):\n            continue", 1)
    src = src.replace("if value_num is None and not value_text:",
                      "if value_num is not None and not _value_is_plausible(value_num):\n                continue\n        if value_num is None and not value_text:", 1)
    open(p, "w", encoding="utf-8").write(src)
    import ast; ast.parse(src)
    print("OK: parser aggiornato e sintassi verificata")
else:
    print("OK: parser gia' aggiornato")
'@

Write-Host "[2/5] Riavvio il backend di test..." -ForegroundColor Cyan
docker compose -f docker-compose.test-ocr.yml restart backend | Out-Null

Write-Host "[3/5] Pulisco le bozze errate (i valori gia' CONFERMATI da te non vengono toccati)..." -ForegroundColor Cyan
docker exec vitasync-pg-test psql -U vitasync -d vitasync -c "DELETE FROM lab_tests WHERE confirmed_by_user = false;"

Write-Host "[4/5] Controllo che il backend sia attivo..." -ForegroundColor Cyan
Start-Sleep -Seconds 8
Invoke-RestMethod http://localhost:8001/health | ConvertTo-Json -Depth 3

Write-Host "[5/5] Fatto!" -ForegroundColor Green
Write-Host "Adesso: apri http://localhost:3002 , vai su Documenti, apri il referto e premi 'Estrai'."
Write-Host "Non dovresti piu' vedere indirizzi/telefoni tra i valori ne' errori 'Failed to fetch'."
