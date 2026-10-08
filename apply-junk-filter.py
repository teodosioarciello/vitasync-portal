"""
apply-junk-filter.py — applica la fix "filtro righe junk + anti-overflow" a
backend/app/services/extraction.py in MODO ROBUSTO (non dipende da line-number
o context del patch, quindi funziona anche se il file locale differisce).

Uso (dalla radice del repo, dentro Docker o con Python di sistema):
    python apply-junk-filter.py            # applica
    python apply-junk-filter.py --check    # verifica senza scrivere

Richiede solo: il file backend/app/services/extraction.py.
"""
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "backend" / "app" / "services" / "extraction.py"

# ---------------------------------------------------------------------------
# BLOCCO 1: costanti + funzioni helper, da inserire DOPO HEADER_KEYWORDS = {...}
# ---------------------------------------------------------------------------
HELPERS = '''
# Parole che indicano righe di intestazione/footer/indirizzi/firme: mai esami.
JUNK_LINE_WORDS = {
    "pag", "pagina", "tel", "telefono", "fax", "email", "e-mail", "www",
    "http", "https", "via", "viale", "corso", "piazza", "piazzale", "vicolo",
    "indirizzo", "referto", "referti", "sottoscritto", "firmato", "firma",
    "digitale", "digitalmente", "legge", "normativa", "d.lgs", "dlgs",
    "artt", "art", "comma", "autorizzazione", "aut.", "note", "nota",
    "avvertenza", "avvertenze", "metodo", "letto", "eseguito", "prelevato",
    "ricevuto",
}

# Se compaiono come PRIME parole della riga, la riga e' una frase (footer),
# non un nome di esame.
JUNK_LEADING_WORDS = {
    "medico", "medica", "dott", "dott.ssa", "dottore", "dottoressa",
    "laboratorio", "synlab", "firma", "firmato", "referto", "pag", "pagina",
}

# Valori numerici oltre questi limiti sono quasi sempre artefatti
# (date, CAP, telefoni, importi), non valori di laboratorio.
MAX_PLAUSIBLE_VALUE = 1_000_000.0
MAX_NAME_TOKENS = 6


def _is_junk_line(line: str) -> bool:
    """True se la riga sembra intestazione/footer/indirizzo/testo legale."""
    upper = line.upper()
    if re.search(r"\\bPAGINA\\s+\\d+\\b", upper):
        return True
    if re.fullmatch(r"(?i)pag\\.?\\s*\\d+\\s*(/\\s*\\d+)?", line.strip()):
        return True
    if re.search(r"(?i)\\b(via|viale|corso|piazza|piazzale|vicolo)\\s+[a-z\\u00e0\\u00e8\\u00e9\\u00ec\\u00f2\\u00f90-9]", line):
        return True
    if re.search(r"(?i)(www\\.|https?://|@[\\w.-]+\\.\\w{2,})", line):
        return True
    if re.search(r"(?i)\\b(tel|fax)[.\\s:/]*[\\d\\s.+]{6,}", line):
        return True
    if re.search(r"(?i)\\b(d\\.?\\s*lgs|artt?\\.?)\\s*\\.?\\s*\\d", line):
        return True
    if re.search(r"(?i)\\bfirma\\s+digitale\\b", line):
        return True
    # righe tipo "AUT. MIN. SAL. N. 1234 DEL 01/01/2010" (autorizzazioni ministeriali)
    if re.search(r"(?i)\\baut\\.?\\s+min", line) or re.search(r"(?i)\\bautorizz", line):
        return True
    words = {re.sub(r"[.:,;()]+$", "", w.lower()) for w in line.split()}
    if words & JUNK_LINE_WORDS:
        return True
    first_words = [re.sub(r"[.:,;()]+$", "", w.lower()) for w in line.split()[:2]]
    if any(w in JUNK_LEADING_WORDS for w in first_words):
        return True
    return False


def _value_is_plausible(num) -> bool:
    if num is None:
        return True  # valore testuale (es. "negativo"): passa
    return abs(num) <= MAX_PLAUSIBLE_VALUE

'''

# ---------------------------------------------------------------------------
# BLOCCO 2: filtro junk all'interno del loop di parse_lab_lines
# (dopo il controllo header keywords)
# ---------------------------------------------------------------------------
import re as _re

# pattern robusto: accetta sia "for t in tokens" sia "for t in tokens[:3]" ecc.
_LOOP_RE = _re.compile(
    r'(^( *)if any\(t\.upper\(\)\.strip\("\(\):\."\) in HEADER_KEYWORDS for t in tokens[^)]*\):\n'
    r'\2 {4}continue\n)',
    _re.MULTILINE,
)

def _insert_junk_check(src: str) -> str:
    m = _LOOP_RE.search(src)
    if not m:
        raise SystemExit("Non trovo il controllo HEADER_KEYWORDS nel loop (formato diverso).")
    indent = m.group(2)
    addition = f"\n{indent}if _is_junk_line(line):\n{indent}    continue\n"
    return src[: m.end()] + addition + src[m.end():]

# ---------------------------------------------------------------------------
# BLOCCO 3: nomi troppo lunghi + plausibilita' valori
# sostituisce il pezzo "name = ... / value_raw = ..." fino a "value_num, value_text = parse_value(value_raw)"
# ---------------------------------------------------------------------------
OLD_TAIL = '''        name = " ".join(tokens[:idx_val]).strip()
        if not name:
            continue

        value_raw = tokens[idx_val]
        rest = tokens[idx_val + 1 :]
        unit, range_str = extract_unit_and_range(rest)

        value_num, value_text = parse_value(value_raw)
'''

NEW_TAIL = '''        name = " ".join(tokens[:idx_val]).strip()
        if not name:
            continue

        # nomi troppo lunghi non sono nomi di esami (frasi, note legali...)
        if len(name.split()) > MAX_NAME_TOKENS:
            continue

        value_raw = tokens[idx_val]
        rest = tokens[idx_val + 1 :]
        unit, range_str = extract_unit_and_range(rest)

        value_num, value_text = parse_value(value_raw)

        # scarta valori numericamente implausibili (date, telefoni, CAP):
        # se il primo token numerico non e' plausibile, cerca il successivo
        if value_num is not None and not _value_is_plausible(value_num):
            first_bad = idx_val
            idx_val = None
            for j in range(first_bad + 1, len(tokens)):
                if is_value_token(tokens[j]):
                    n2, _ = parse_value(tokens[j])
                    if n2 is None or _value_is_plausible(n2):
                        idx_val = j
                        break
            if idx_val is None:
                continue
            name = " ".join(tokens[:idx_val]).strip()
            if not name or len(name.split()) > MAX_NAME_TOKENS:
                continue
            value_raw = tokens[idx_val]
            rest = tokens[idx_val + 1 :]
            unit, range_str = extract_unit_and_range(rest)
            value_num, value_text = parse_value(value_raw)
'''

HEADER_END_MARK = '}\n\n\ndef '  # fine del set HEADER_KEYWORDS prima della prima funzione


def apply(src: str) -> str:
    if "_is_junk_line" in src:
        raise SystemExit("La fix risulta GIA' applicata (trovato _is_junk_line).")

    # BLOCCO 1: inserisci helper dopo HEADER_KEYWORDS
    i = src.find("HEADER_KEYWORDS")
    if i == -1:
        raise SystemExit("Non trovo HEADER_KEYWORDS: file diverso dal previsto.")
    j = src.find("}", i)
    if j == -1:
        raise SystemExit("Non trovo la chiusura di HEADER_KEYWORDS.")
    insert_at = j + 1
    src = src[:insert_at] + "\n" + HELPERS + src[insert_at:]

    # BLOCCO 2: filtro junk nel loop (regex robusta su indentazione/slice)
    src = _insert_junk_check(src)

    # BLOCCO 3: tail con plausibilita' (search anch'esso regex-tolerant)
    if OLD_TAIL not in src:
        raise SystemExit("Non trovo il blocco 'name = ... parse_value' (formato diverso).")
    src = src.replace(OLD_TAIL, NEW_TAIL, 1)

    return src


def main():
    check = "--check" in sys.argv
    src = TARGET.read_text(encoding="utf-8")
    try:
        out = apply(src)
    except SystemExit as e:
        print("ERRORE:", e)
        sys.exit(1)

    compile(out, str(TARGET), "exec")  # sintassi valida?
    if check:
        print("CHECK OK: la fix puo' essere applicata.")
        return
    TARGET.write_text(out, encoding="utf-8")
    print(f"FATTO: fix applicata a {TARGET}")
    print("Ora ricostruisci il container:")
    print('  docker compose -f docker-compose.test-ocr.yml up -d --build vitasync-backend-test')


if __name__ == "__main__":
    main()
