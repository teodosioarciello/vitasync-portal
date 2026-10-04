import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, KeepTogether,
)

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Patient, Document, LabTest
from app.db.therapy_models import Medicine, Therapy, Reminder
from app.db.audit_models import AuditLog

WATERMARK_TEXT = "VitaSync - Bozza personale - Verificare con medico"
PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 30 * mm


def _add_watermark(canv, _doc):
    canv.saveState()
    canv.setFillColor(colors.Color(0.78, 0.78, 0.78, 0.18))
    canv.setFont("Helvetica-Bold", 24)
    canv.translate(PAGE_W / 2, PAGE_H / 2)
    canv.rotate(45)
    canv.drawCentredString(0, 0, WATERMARK_TEXT)
    canv.restoreState()


def _count(model):
    if model is None:
        return 0
    try:
        with SessionLocal() as db:
            return int(db.query(model).count())
    except Exception:
        return -1


def _count_confirmed():
    try:
        with SessionLocal() as db:
            return int(db.query(LabTest).filter(LabTest.confirmed_by_user.is_(True)).count())
    except Exception:
        return -1


def _count_active_docs():
    try:
        with SessionLocal() as db:
            return int(db.query(Document).filter(Document.deleted_at.is_(None)).count())
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# STILI
# ---------------------------------------------------------------------------
def _build_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=32, leading=38, alignment=1, spaceAfter=6*mm, textColor=colors.HexColor("#0f172a")))
    s.add(ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=16, leading=20, alignment=1, spaceAfter=3*mm, textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle("CoverMeta", fontName="Helvetica-Oblique", fontSize=11, leading=14, alignment=1, spaceAfter=2*mm, textColor=colors.HexColor("#64748b")))
    s.add(ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=20, leading=24, spaceBefore=12*mm, spaceAfter=5*mm, textColor=colors.HexColor("#0f172a"), borderPadding=(0,0,2,0)))
    s.add(ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceBefore=8*mm, spaceAfter=3*mm, textColor=colors.HexColor("#1e293b")))
    s.add(ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=5*mm, spaceAfter=2*mm, textColor=colors.HexColor("#334155")))
    s.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=2*mm, textColor=colors.HexColor("#1e293b")))
    s.add(ParagraphStyle("BodyBold", fontName="Helvetica-Bold", fontSize=10, leading=14, spaceAfter=2*mm, textColor=colors.HexColor("#1e293b")))
    s.add(ParagraphStyle("Small", fontName="Helvetica", fontSize=8.5, leading=11, spaceAfter=1.5*mm, textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle("VitaCode", fontName="Courier", fontSize=8.5, leading=11, spaceAfter=2*mm, backColor=colors.HexColor("#f1f5f9"), leftIndent=4*mm, rightIndent=4*mm, borderPadding=(3,3,3,3), textColor=colors.HexColor("#0f172a")))
    s.add(ParagraphStyle("TableCell", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#1e293b")))
    s.add(ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white))
    s.add(ParagraphStyle("DiagramCell", fontName="Courier", fontSize=8, leading=10, textColor=colors.HexColor("#334155"), alignment=1))
    s.add(ParagraphStyle("Footer", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.HexColor("#94a3b8")))
    s.add(ParagraphStyle("TOCEntry", fontName="Helvetica", fontSize=11, leading=16, leftIndent=6*mm, textColor=colors.HexColor("#1e293b")))
    s.add(ParagraphStyle("TOCTitle", fontName="Helvetica-Bold", fontSize=11, leading=16, textColor=colors.HexColor("#0f172a")))
    return s


# ---------------------------------------------------------------------------
# HELPERS TABELLE
# ---------------------------------------------------------------------------
def _header_table(headers, rows, col_widths=None):
    hdr = [Paragraph(h, _st["TableHeader"]) for h in headers]
    data = [hdr]
    for row in rows:
        data.append([Paragraph(str(c), _st["TableCell"]) for c in row])
    if col_widths is None:
        col_widths = [CONTENT_W / len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    return t


def _kv_table(rows):
    data = [[Paragraph(r[0], _st["BodyBold"]), Paragraph(r[1], _st["TableCell"])] for r in rows]
    t = Table(data, colWidths=[55*mm, CONTENT_W - 55*mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f1f5f9")),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    return t


def _diagram_box(lines, title=None):
    """Crea un box ASCII-art come tabella ReportLab."""
    elements = []
    if title:
        elements.append(Paragraph(title, _st["H3"]))
    max_len = max(len(l) for l in lines) if lines else 20
    border = "+" + "-" * (max_len + 2) + "+"
    formatted = [border]
    for line in lines:
        formatted.append("| " + line.ljust(max_len) + " |")
    formatted.append(border)
    cell_text = "<br/>".join(formatted)
    data = [[Paragraph(cell_text.replace(" ", "&nbsp;"), _st["DiagramCell"])]]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#94a3b8")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    elements.append(t)
    return elements


def _flow_diagram(steps):
    """Crea un flowchart verticale semplice."""
    elements = []
    for i, step in enumerate(steps):
        box_lines = [step]
        max_len = max(len(step), 30)
        border = "+" + "-" * (max_len + 2) + "+"
        formatted = [border, "| " + step.ljust(max_len) + " |", border]
        cell_text = "<br/>".join(formatted)
        data = [[Paragraph(cell_text.replace(" ", "&nbsp;"), _st["DiagramCell"])]]
        t = Table(data, colWidths=[CONTENT_W * 0.7])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#eff6ff")),
            ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#3b82f6")),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        elements.append(t)
        if i < len(steps) - 1:
            arrow_data = [[Paragraph("|<br/>v", _st["DiagramCell"])]]
            at = Table(arrow_data, colWidths=[CONTENT_W * 0.7])
            at.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
            elements.append(at)
    return elements


def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceBefore=3*mm, spaceAfter=3*mm)


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------
_st = None  # globale per helpers

def build_pdf():
    global _st
    _st = _build_styles()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%d/%m/%Y %H:%M UTC")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        title="VitaSync Portal - Specifica Funzionale",
        author="VitaSync Portal",
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )
    story = []

    # =====================================================================
    # COPERTINA
    # =====================================================================
    story.append(Spacer(1, 50*mm))
    story.append(Paragraph("VitaSync Portal", _st["CoverTitle"]))
    story.append(Paragraph("Specifica Funzionale di Progetto", _st["CoverSub"]))
    story.append(Spacer(1, 8*mm))
    story.append(_hr())
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Versione: 1.0", _st["CoverMeta"]))
    story.append(Paragraph("Data: " + ts, _st["CoverMeta"]))
    story.append(Paragraph("Stato: Release Candidate", _st["CoverMeta"]))
    story.append(Paragraph("Classificazione: Uso Interno / Personale-Familiare", _st["CoverMeta"]))
    story.append(Spacer(1, 15*mm))
    story.append(Paragraph(
        "Questo documento descrive l'architettura, i modelli dati, le API, i flussi funzionali, "
        "la sicurezza e lo stato attuale del sistema VitaSync Portal. "
        "Non costituisce parere medico.",
        _st["Body"],
    ))
    story.append(PageBreak())

    # =====================================================================
    # INDICE
    # =====================================================================
    story.append(Paragraph("Indice", _st["H1"]))
    toc_items = [
        ("1.", "Panoramica e Obiettivi"),
        ("2.", "Architettura di Sistema"),
        ("3.", "Stack Tecnologico"),
        ("4.", "Modello Dati"),
        ("5.", "API REST - Specifica Endpoint"),
        ("6.", "Flussi Funzionali"),
        ("7.", "Frontend - Pagine e Componenti"),
        ("8.", "Sicurezza e Hardening"),
        ("9.", "Accessibilita' (WCAG)"),
        ("10.", "Refinement UI"),
        ("11.", "Report PDF e Watermark"),
        ("12.", "Backup e Disaster Recovery"),
        ("13.", "Stato Dati Attuale"),
        ("14.", "Roadmap e Evoluzioni Future"),
        ("15.", "Glossario"),
        ("16.", "Disclaimer e Limiti"),
    ]
    for num, title in toc_items:
        story.append(Paragraph(num + "  " + title, _st["TOCEntry"]))
    story.append(PageBreak())

    # =====================================================================
    # 1. PANORAMICA
    # =====================================================================
    story.append(Paragraph("1. Panoramica e Obiettivi", _st["H1"]))
    story.append(Paragraph(
        "VitaSync Portal e' un'applicazione web self-hosted per l'organizzazione personale e familiare "
        "di documenti sanitari, referti di laboratorio, terapie, promemoria e notifiche. Il sistema "
        "permette di caricare referti PDF/immagine, estrarre automaticamente i valori di laboratorio, "
        "confermarli manualmente, visualizzarne il trend storico e generare un report PDF riepilogativo "
        "da portare al medico curante.",
        _st["Body"],
    ))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("1.1 Obiettivi Funzionali", _st["H2"]))
    objectives = [
        ("OF-01", "Archiviazione sicura di referti sanitari con metadata strutturati"),
        ("OF-02", "Estrazione automatica valori di laboratorio da PDF testuali e immagini OCR"),
        ("OF-03", "Conferma manuale obbligatoria di ogni valore estratto prima dell'uso clinico"),
        ("OF-04", "Visualizzazione trend storici dei valori confermati con grafici SVG"),
        ("OF-05", "Generazione report PDF riepilogativo con watermark 'bozza personale'"),
        ("OF-06", "Gestione catalogo medicinali e terapie attive/paused/completate"),
        ("OF-07", "Promemoria schedulabili legati a terapie o generici"),
        ("OF-08", "Notifiche multi-canale (console log / SMTP cifrato)"),
        ("OF-09", "Audit log completo di tutte le azioni sensibili"),
        ("OF-10", "Accessibilita' WCAG: skip link, ARIA, label associate, tabelle semantiche"),
    ]
    story.append(_header_table(
        ["ID", "Obiettivo"],
        objectives,
        col_widths=[18*mm, CONTENT_W - 18*mm],
    ))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("1.2 Non-Obiettivi (Out of Scope)", _st["H2"]))
    non_obj = [
        "Diagnosi medica o valutazione clinica automatica",
        "Interazioni farmacologiche o consigli terapeutici",
        "Integrazione con fascicolo sanitario elettronico nazionale",
        "Multi-tenancy pubblica o registrazione aperta",
        "AI integrata per valutazione automatica dei valori",
    ]
    for n in non_obj:
        story.append(Paragraph("- " + n, _st["Body"]))
    story.append(PageBreak())

    # =====================================================================
    # 2. ARCHITETTURA
    # =====================================================================
    story.append(Paragraph("2. Architettura di Sistema", _st["H1"]))
    story.append(Paragraph("2.1 Diagramma Architetturale", _st["H2"]))
    arch_lines = [
        "                    +------------------+",
        "                    |   UTENTE/BROWSER |",
        "                    +--------+---------+",
        "                             |",
        "                    HTTPS / Cookie Session",
        "                             |",
        "                    +--------v---------+",
        "                    |  NEXT.JS 14 APP  |",
        "                    |  (Port 3001)     |",
        "                    +--------+---------+",
        "                             |",
        "                      REST API JSON",
        "                             |",
        "                    +--------v---------+",
        "                    |   FASTAPI BACKEND |",
        "                    |   (Port 8000)    |",
        "                    +--+-----+------+--+",
        "                       |     |      |",
        "              +--------+  +--+---+  +--------+",
        "              |             |               |",
        "     +--------v------+ +---v----+ +--------v------+",
        "     | PostgreSQL 16 | | Redis 7| | Local Storage |",
        "     | (Port 5432)   | |(6379)  | | (Volume/Disk) |",
        "     +---------------+ +--------+ +---------------+",
    ]
    story.extend(_diagram_box(arch_lines, "Architettura a 4 Container Docker"))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("2.2 Componenti Backend", _st["H2"]))
    components = [
        ("FastAPI App", "app/main.py", "Router, middleware security/audit/ratelimit, lifespan"),
        ("Auth Router", "app/api/auth.py", "Login, register, logout, verify-email, password-reset"),
        ("Documents Router", "app/api/documents.py", "Upload, list, trash, restore, delete, extract"),
        ("Lab Tests Router", "app/api/lab_tests.py", "CRUD valori, confirm, codes, trend"),
        ("Medicines Router", "app/api/medicines.py", "CRUD catalogo medicinali"),
        ("Therapies Router", "app/api/therapies.py", "CRUD terapie con validazioni"),
        ("Reminders Router", "app/api/reminders.py", "CRUD promemoria schedulati"),
        ("Notifications Router", "app/api/notifications.py", "Lista, mark-read, stato reminders"),
        ("Reports Router", "app/api/reports.py", "Generazione PDF riepilogativo on-the-fly"),
        ("Settings Router", "app/api/settings.py", "Preferenze utente + config SMTP"),
        ("Extraction Service", "app/services/extraction.py", "Parser deterministico + sinonimi OCR"),
        ("OCR Service", "app/services/ocr.py", "PyMuPDF raster + Tesseract fallback"),
        ("Medical Report", "app/services/medical_report.py", "ReportLab PDF con watermark diagonale"),
        ("Storage Service", "app/services/storage.py", "Persistenza locale/MinIO + sanitizzazione"),
        ("Upload Validation", "app/services/upload_validation.py", "Magic bytes + limite dimensione"),
        ("Audit Service", "app/services/audit.py", "Middleware + record_audit helper"),
        ("Config", "app/core/config.py", "Pydantic Settings da .env"),
    ]
    story.append(_header_table(
        ["Componente", "File", "Responsabilita'"],
        components,
        col_widths=[38*mm, 52*mm, CONTENT_W - 90*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 3. STACK
    # =====================================================================
    story.append(Paragraph("3. Stack Tecnologico", _st["H1"]))
    stack = [
        ("Backend Framework", "FastAPI 0.115.6", "Async, Pydantic v2, OpenAPI auto"),
        ("ORM", "SQLAlchemy 2.0.36", "Mapped columns, session scoped"),
        ("Database", "PostgreSQL 16-alpine", "JSONB, UUID, CheckConstraint"),
        ("Cache/Session", "Redis 7-alpine", "Rate limiting keys, session store"),
        ("PDF Generation", "ReportLab >=4.2.0", "SimpleDocTemplate, watermark callback"),
        ("PDF Parsing", "PyMuPDF 1.24.10", "Text extraction + raster pixmap"),
        ("OCR", "pytesseract 0.3.13 + Pillow 11.0", "Fallback per PDF scansionati/immagini"),
        ("Password Hashing", "argon2-cffi 23.1.0", "Argon2id per credenziali utente"),
        ("Cifratura", "cryptography >=41.0.0", "Fernet per password SMTP"),
        ("Frontend", "Next.js 14.2.x", "App Router, SSR, React Server Components"),
        ("CSS Framework", "Tailwind CSS", "Utility-first, design token coerenti"),
        ("Container Runtime", "Docker Compose v2", "4 servizi orchestrati"),
        ("Validazione Input", "Pydantic 2.10.4", "Schema validation request/response"),
        ("Email Validation", "email-validator 2.2.0", "Verifica formato email"),
        ("File Upload", "python-multipart 0.0.20", "Form data + file streaming"),
    ]
    story.append(_header_table(
        ["Layer", "Tecnologia", "Note"],
        stack,
        col_widths=[38*mm, 52*mm, CONTENT_W - 90*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 4. MODELLO DATI
    # =====================================================================
    story.append(Paragraph("4. Modello Dati", _st["H1"]))
    story.append(Paragraph("4.1 Diagramma ER (Entita'-Relazioni)", _st["H2"]))
    er_lines = [
        "  +----------+       +-----------+       +----------+",
        "  |  Family  |1-----N|FamilyMember|N-----1|   User   |",
        "  +----------+       +-----------+       +----------+",
        "       |1                                    |1",
        "       |N                                    |N",
        "  +----------+                          +-----------+",
        "  | Patient  |                          |  Session  |",
        "  +----------+                          +-----------+",
        "       |1                                     ",
        "       |N                                     ",
        "  +----------+       +----------+             ",
        "  | Document |1-----N| LabTest  |             ",
        "  +----------+       +----------+             ",
        "       |                                      ",
        "       | (patient_id)                         ",
        "       |                                      ",
        "  +----------+       +----------+       +----------+",
        "  | Medicine |1-----N| Therapy  |1-----N| Reminder |",
        "  +----------+       +----------+       +----------+",
        "                                            ",
        "  +------------+                            ",
        "  |  AuditLog  | (user_id, action, timestamp)",
        "  +------------+                            ",
    ]
    story.extend(_diagram_box(er_lines, "Diagramma Entita'-Relazioni"))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("4.2 Tabella: users", _st["H2"]))
    story.append(_header_table(
        ["Colonna", "Tipo", "Vincoli", "Descrizione"],
        [
            ("id", "UUID", "PK, default uuid4", "Identificativo univoco utente"),
            ("username", "VARCHAR(80)", "UNIQUE, NOT NULL, INDEX", "Nome utente login"),
            ("email", "VARCHAR(255)", "UNIQUE, NOT NULL, INDEX", "Email verificata"),
            ("password_hash", "VARCHAR(255)", "NOT NULL", "Hash Argon2id"),
            ("full_name", "VARCHAR(160)", "NULLABLE", "Nome completo opzionale"),
            ("birth_date", "DATE", "NULLABLE", "Data nascita"),
            ("is_active", "BOOLEAN", "DEFAULT true", "Account attivo"),
            ("email_verified", "BOOLEAN", "DEFAULT false", "Email verificata"),
            ("accepted_privacy_at", "TIMESTAMPTZ", "NULLABLE", "Consenso privacy"),
            ("accepted_terms_at", "TIMESTAMPTZ", "NULLABLE", "Accettazione termini"),
            ("created_at", "TIMESTAMPTZ", "DEFAULT utcnow", "Creazione account"),
            ("updated_at", "TIMESTAMPTZ", "ON UPDATE utcnow", "Ultima modifica"),
        ],
        col_widths=[32*mm, 30*mm, 42*mm, CONTENT_W - 104*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4.3 Tabella: patients", _st["H2"]))
    story.append(_header_table(
        ["Colonna", "Tipo", "Vincoli", "Descrizione"],
        [
            ("id", "UUID", "PK, default uuid4", "Identificativo paziente"),
            ("family_id", "UUID", "FK families.id, CASCADE", "Famiglia di appartenenza"),
            ("display_name", "VARCHAR(160)", "NOT NULL", "Nome visualizzato"),
            ("birth_date", "DATE", "NULLABLE", "Data nascita"),
            ("sex", "VARCHAR(16)", "CHECK IN (M,F,X,unknown)", "Sesso biologico"),
            ("height_cm", "NUMERIC(5,2)", "NULLABLE", "Altezza in cm"),
            ("relationship_to_owner", "VARCHAR(32)", "CHECK, DEFAULT self", "Relazione con owner"),
            ("is_minor", "BOOLEAN", "DEFAULT false", "Minorenne"),
            ("legal_representative_user_id", "UUID", "FK users.id, NULLABLE", "Tutore legale"),
            ("consent_status", "VARCHAR(32)", "CHECK, DEFAULT pending", "Stato consenso"),
            ("notes", "TEXT", "NULLABLE", "Note libere"),
            ("created_at", "TIMESTAMPTZ", "DEFAULT utcnow", "Creazione"),
            ("updated_at", "TIMESTAMPTZ", "ON UPDATE utcnow", "Ultima modifica"),
        ],
        col_widths=[38*mm, 28*mm, 42*mm, CONTENT_W - 108*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4.4 Tabella: documents", _st["H2"]))
    story.append(_header_table(
        ["Colonna", "Tipo", "Vincoli", "Descrizione"],
        [
            ("id", "UUID", "PK", "Identificativo documento"),
            ("patient_id", "UUID", "FK patients.id, CASCADE", "Paziente associato"),
            ("uploaded_by_user_id", "UUID", "FK users.id", "Utente che ha caricato"),
            ("title", "VARCHAR(255)", "NOT NULL", "Titolo documento"),
            ("document_type", "VARCHAR(64)", "CHECK IN (...)", "lab_report, urine_report, prescription, imaging, medical_letter, nutrition_report, other"),
            ("source_filename", "VARCHAR(255)", "NOT NULL", "Nome file originale sanificato"),
            ("storage_key", "VARCHAR(512)", "NOT NULL", "Path relativo nello storage"),
            ("mime_type", "VARCHAR(128)", "NOT NULL", "MIME rilevato da magic bytes"),
            ("size_bytes", "INTEGER", "NOT NULL", "Dimensione file"),
            ("sha256", "VARCHAR(64)", "NOT NULL", "Hash SHA-256 integrita'"),
            ("document_date", "DATE", "NULLABLE", "Data referto"),
            ("processing_status", "VARCHAR(32)", "CHECK, DEFAULT pending", "pending/processing/completed/failed"),
            ("ai_status", "VARCHAR(32)", "CHECK, DEFAULT disabled", "Stato elaborazione AI"),
            ("metadata_json", "JSONB", "DEFAULT {}", "Metadata estrazione/parser"),
            ("deleted_at", "TIMESTAMPTZ", "NULLABLE, INDEX", "Soft delete timestamp"),
            ("created_at", "TIMESTAMPTZ", "DEFAULT utcnow", "Upload timestamp"),
        ],
        col_widths=[35*mm, 28*mm, 42*mm, CONTENT_W - 105*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4.5 Tabella: lab_tests", _st["H2"]))
    story.append(_header_table(
        ["Colonna", "Tipo", "Vincoli", "Descrizione"],
        [
            ("id", "UUID", "PK", "Identificativo valore"),
            ("document_id", "UUID", "FK documents.id, CASCADE", "Documento sorgente"),
            ("patient_id", "UUID", "FK patients.id, CASCADE", "Paziente"),
            ("test_code", "VARCHAR(64)", "NOT NULL, INDEX", "Codice normalizzato (es. glucose)"),
            ("test_name_original", "VARCHAR(255)", "NOT NULL", "Nome originale dal referto"),
            ("test_name_normalized", "VARCHAR(128)", "NOT NULL, INDEX", "Nome normalizzato display"),
            ("value_numeric", "NUMERIC(12,4)", "NULLABLE", "Valore numerico"),
            ("value_text", "TEXT", "NULLABLE", "Valore testuale se non numerico"),
            ("unit", "VARCHAR(64)", "NULLABLE", "Unita' di misura"),
            ("reference_min", "NUMERIC(12,4)", "NULLABLE", "Limite inferiore range"),
            ("reference_max", "NUMERIC(12,4)", "NULLABLE", "Limite superiore range"),
            ("reference_text", "TEXT", "NULLABLE", "Range testuale originale"),
            ("flag", "VARCHAR(32)", "CHECK IN (normal,above_range,below_range,critical,unknown)", "Flag calcolato"),
            ("confidence", "NUMERIC", "NULLABLE", "Confidenza normalizzazione (0-1)"),
            ("confirmed_by_user", "BOOLEAN", "DEFAULT false", "Confermato dall'utente"),
            ("user_corrected", "BOOLEAN", "DEFAULT false", "Corretto manualmente"),
            ("extracted_at", "TIMESTAMPTZ", "DEFAULT utcnow", "Timestamp estrazione"),
        ],
        col_widths=[35*mm, 28*mm, 48*mm, CONTENT_W - 111*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4.6 Tabelle Terapie (therapy_models)", _st["H2"]))
    story.append(_header_table(
        ["Tabella", "Colonne Chiave", "Descrizione"],
        [
            ("medicines", "id, patient_id, name, generic_name, form, strength, notes", "Catalogo medicinali familiare"),
            ("therapies", "id, patient_id, medicine_id, status, dose, frequency, route, start_date, end_date, instructions, notes", "Terapia attiva/paused/completata"),
            ("reminders", "id, patient_id, therapy_id, reminder_type, scheduled_at, status, title, notes", "Promemoria schedulato"),
        ],
        col_widths=[28*mm, 72*mm, CONTENT_W - 100*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4.7 Tabella: audit_logs", _st["H2"]))
    story.append(_header_table(
        ["Colonna", "Tipo", "Descrizione"],
        [
            ("id", "UUID", "Identificativo evento"),
            ("action", "VARCHAR", "Azione (es. document.upload, lab_test.confirm)"),
            ("method", "VARCHAR", "HTTP method o SYSTEM"),
            ("path", "VARCHAR", "Endpoint o script path"),
            ("status_code", "INTEGER", "HTTP status code"),
            ("ip_address", "VARCHAR(45)", "IP client"),
            ("user_agent", "TEXT", "User-Agent header"),
            ("user_id", "UUID", "Utente autenticato"),
            ("extra", "TEXT", "Contesto aggiuntivo strutturato"),
            ("created_at", "TIMESTAMPTZ", "Timestamp evento"),
        ],
        col_widths=[30*mm, 30*mm, CONTENT_W - 60*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 5. API REST
    # =====================================================================
    story.append(Paragraph("5. API REST - Specifica Endpoint", _st["H1"]))
    story.append(Paragraph("5.1 Autenticazione", _st["H2"]))
    story.append(_header_table(
        ["Method", "Path", "Auth", "Descrizione"],
        [
            ("POST", "/api/auth/register", "No", "Registrazione nuovo utente + invite code"),
            ("POST", "/api/auth/login", "No", "Login con username/email + password. Rate limit: 10/5min"),
            ("POST", "/api/auth/logout", "Si'", "Invalidazione sessione"),
            ("POST", "/api/auth/verify-email", "No", "Verifica email tramite token"),
            ("GET", "/api/auth/me", "Si'", "Profilo utente corrente"),
        ],
        col_widths=[18*mm, 48*mm, 14*mm, CONTENT_W - 80*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("5.2 Documenti", _st["H2"]))
    story.append(_header_table(
        ["Method", "Path", "Auth", "Descrizione"],
        [
            ("POST", "/api/documents/upload", "Si' (write)", "Upload referto. Query: patient_id. Form: title, document_type, file"),
            ("GET", "/api/documents", "Si' (read)", "Lista documenti attivi. Query: patient_id"),
            ("GET", "/api/documents/trash", "Si' (read)", "Lista documenti nel cestino"),
            ("GET", "/api/documents/{id}", "Si' (read)", "Dettaglio singolo documento"),
            ("POST", "/api/documents/{id}/extract", "Si' (read)", "Estrazione valori. Ritorna lista LabTest bozze"),
            ("POST", "/api/documents/{id}/lab-tests/confirm-all", "Si' (write)", "Conferma tutti i valori non confermati del documento"),
            ("POST", "/api/documents/{id}/restore", "Si' (write)", "Ripristina documento dal cestino"),
            ("DELETE", "/api/documents/{id}", "Si' (write)", "Soft delete (sposta nel cestino)"),
            ("DELETE", "/api/documents/{id}/permanent", "Si' (write)", "Eliminazione definitiva + rimozione file storage"),
        ],
        col_widths=[18*mm, 62*mm, 20*mm, CONTENT_W - 100*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("5.3 Lab Tests", _st["H2"]))
    story.append(_header_table(
        ["Method", "Path", "Auth", "Descrizione"],
        [
            ("GET", "/api/lab-tests", "Si'", "Lista valori. Query: document_id, patient_id, confirmed"),
            ("PATCH", "/api/lab-tests/{id}", "Si'", "Aggiorna singolo valore (conferma, correzione)"),
            ("GET", "/api/lab-tests/codes", "Si'", "Lista codici esame unici con conteggio punti"),
            ("GET", "/api/lab-tests/trend", "Si'", "Dati trend per un test_code. Query: test_code, patient_id"),
        ],
        col_widths=[18*mm, 52*mm, 14*mm, CONTENT_W - 84*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("5.4 Medicinali / Terapie / Promemoria", _st["H2"]))
    story.append(_header_table(
        ["Method", "Path", "Auth", "Descrizione"],
        [
            ("GET/POST", "/api/medicines", "Si'", "CRUD catalogo medicinali"),
            ("GET/POST", "/api/therapies", "Si'", "CRUD terapie con validazione medicina esistente"),
            ("GET/POST", "/api/reminders", "Si'", "CRUD promemoria. Filtro per stato"),
            ("GET", "/api/notifications", "Si'", "Lista notifiche"),
            ("PATCH", "/api/notifications/{id}/read", "Si'", "Marca notifica come letta"),
            ("GET", "/api/notifications/reminders-status", "Si'", "Stato promemoria pendenti/scaduti"),
        ],
        col_widths=[18*mm, 58*mm, 14*mm, CONTENT_W - 90*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("5.5 Report e Settings", _st["H2"]))
    story.append(_header_table(
        ["Method", "Path", "Auth", "Descrizione"],
        [
            ("GET", "/api/reports/medical-summary.pdf", "Si'", "Genera PDF riepilogativo on-the-fly. Solo valori confermati da documenti attivi"),
            ("GET", "/api/settings", "Si'", "Leggi preferenze utente"),
            ("PUT", "/api/settings", "Si'", "Aggiorna preferenze + config SMTP (password cifrata Fernet)"),
            ("GET", "/health", "No", "Health check. Ritorna status, environment, ai_enabled, storage_backend"),
        ],
        col_widths=[18*mm, 62*mm, 14*mm, CONTENT_W - 94*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 6. FLUSSI FUNZIONALI
    # =====================================================================
    story.append(Paragraph("6. Flussi Funzionali", _st["H1"]))

    story.append(Paragraph("6.1 Flusso: Upload + Estrazione + Conferma", _st["H2"]))
    story.extend(_flow_diagram([
        "UTENTE: Carica referto PDF/JPEG/PNG in /documents",
        "BACKEND: Valida magic bytes + dimensione (max 25MB)",
        "BACKEND: Salva file in storage locale patients/{id}/documents/{uuid}/",
        "BACKEND: Crea record Document (status=pending)",
        "BACKEND: Servizio extraction analizza testo (PyMuPDF + OCR fallback)",
        "BACKEND: Normalizza nomi esami con sinonimi + tolleranza OCR",
        "BACKEND: Salva LabTest con confirmed_by_user=False (bozze)",
        "FRONTEND: Utente apre /documents/{id}/review",
        "UTENTE: Rivede valori, corregge se necessario, conferma riga/blocco",
        "BACKEND: Aggiorna LabTest confirmed_by_user=True",
        "RISULTATO: Valori visibili in /trend e nel report PDF",
    ]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("6.2 Flusso: Generazione Report PDF", _st["H2"]))
    story.extend(_flow_diagram([
        "UTENTE: Clicca 'Scarica Riepilogo PDF' in /report",
        "FRONTEND: GET /api/reports/medical-summary.pdf con cookie sessione",
        "BACKEND: Verifica auth + autorizzazione paziente",
        "BACKEND: collect_report_data() query LabTest confermati + Document attivi",
        "BACKEND: build_pdf_bytes() genera PDF in memoria con ReportLab",
        "BACKEND: Applica watermark diagonale su ogni pagina",
        "BACKEND: Record audit event report.medical_summary_download",
        "BACKEND: Ritorna Response application/pdf con Content-Disposition",
        "FRONTEND: Blob download con filename vitasync-riepilogo-esami-YYYYMMDD.pdf",
    ]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("6.3 Flusso: Soft Delete + Restore + Permanent Delete", _st["H2"]))
    story.extend(_flow_diagram([
        "UTENTE: Clicca 'Elimina' su documento in /documents",
        "BACKEND: soft_delete_document() imposta deleted_at=utcnow()",
        "DOCUMENTO: Scompare da lista attiva, appare in /trash",
        "UTENTE: Clicca 'Ripristina' in /trash",
        "BACKEND: restore_document() imposta deleted_at=None",
        "DOCUMENTO: Torna nella lista attiva",
        "UTENTE: Clicca 'Elimina definitivamente' in /trash",
        "BACKEND: permanent_delete_document() rimuove record DB + file storage",
        "AUDIT: Evento document.permanent_delete registrato",
    ]))
    story.append(PageBreak())

    # =====================================================================
    # 7. FRONTEND
    # =====================================================================
    story.append(Paragraph("7. Frontend - Pagine e Componenti", _st["H1"]))
    story.append(Paragraph("7.1 Mappa Pagine App Router", _st["H2"]))
    pages = [
        ("/", "Redirect a /login se non autenticato"),
        ("/login", "Form login email/username + password. Link a /register"),
        ("/register", "Registrazione + invite code. Verify email flow"),
        ("/dashboard", "Hub principale. Card Azioni rapide verso tutte le sezioni"),
        ("/documents", "Upload referti + elenco attivi + cestino. Link a review"),
        ("/documents/[id]/review", "Review valori estratti. Tabella editabile. Conferma riga/blocco"),
        ("/trend", "Select esame + grafico SVG + tile selezionabili + tabella storico"),
        ("/medicines", "Form creazione + tabella elenco medicinali"),
        ("/therapies", "Form creazione terapia + card elenco con badge stato"),
        ("/reminders", "Form creazione + filtro stato + card elenco"),
        ("/notifications", "Lista notifiche + mark read + nota operativa"),
        ("/report", "Download PDF riepilogativo. Info contenuto + disclaimer"),
        ("/settings", "Toggle notifiche + canale console/SMTP + config SMTP cifrata"),
    ]
    story.append(_header_table(
        ["Route", "Funzione"],
        pages,
        col_widths=[55*mm, CONTENT_W - 55*mm],
    ))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("7.2 Libreria Componenti UI (frontend/components/ui/)", _st["H2"]))
    ui_components = [
        ("Alert", "Messaggi info/success/warning/error", "role='alert'/'status', aria-live, aria-atomic"),
        ("Button", "Bottone con varianti primary/secondary/ghost/danger/outlines", "aria-busy durante loading, focus ring, disabled state"),
        ("Card", "Container bianco rounded-2xl shadow", "Padding sm/md/lg configurabile"),
        ("Badge", "Etichetta semantica pill", "Varianti: default/success/warning/danger/info"),
        ("EmptyState", "Stato vuoto con icona + titolo + descrizione + action", "Layout centrato, action slot"),
        ("Input", "Campo input con label + error + hint", "useId auto, htmlFor, aria-invalid, aria-describedby"),
    ]
    story.append(_header_table(
        ["Componente", "Scopo", "Accessibilita'"],
        ui_components,
        col_widths=[28*mm, 62*mm, CONTENT_W - 90*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 8. SICUREZZA
    # =====================================================================
    story.append(Paragraph("8. Sicurezza e Hardening", _st["H1"]))

    story.append(Paragraph("8.1 Autenticazione e Sessioni", _st["H2"]))
    story.append(Paragraph(
        "Autenticazione basata su cookie HTTP-only firmato con secret_key. "
        "Sessione con scadenza configurabile (default 7 giorni). "
        "Rate limiting su /api/auth/login (10 req/5min) e /api/auth/register (5 req/10min). "
        "Verifica email obbligatoria in produzione. Registrazione solo tramite invite code.",
        _st["Body"],
    ))

    story.append(Paragraph("8.2 Cifratura Dati Sensibili", _st["H2"]))
    story.append(Paragraph(
        "Le password SMTP sono cifrate con Fernet (AES-128-CBC + HMAC-SHA256) usando una chiave "
        "derivata dalla variabile d'ambiente FERNET_KEY. La chiave non e' mai memorizzata nel database. "
        "Il round-trip encrypt/decrypt e' verificato da smoke test automatico all'avvio.",
        _st["Body"],
    ))

    story.append(Paragraph("8.3 Validazione Upload", _st["H2"]))
    story.append(_header_table(
        ["Controllo", "Implementazione", "Valore"],
        [
            ("Magic bytes", "Lettura primi 16 byte del file", "%PDF / FF-D8-FF / 89-PNG"),
            ("Dimensione massima", "Configurabile via MAX_UPLOAD_MB", "Default 20 MB (hard cap 25 MB)"),
            ("Sanitizzazione filename", "Rimozione caratteri non alfanumerici", "Max 120 char, safe chars only"),
            ("MIME type", "Rilevato da magic bytes, non da Content-Type", "Previene spoofing"),
            ("SHA-256", "Calcolato durante upload stream", "Integrita' file verificabile"),
            ("Path isolation", "patients/{patient_id}/documents/{uuid}/", "Nessun path traversal possibile"),
        ],
        col_widths=[35*mm, 60*mm, CONTENT_W - 95*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("8.4 Security Headers", _st["H2"]))
    headers = [
        ("X-Content-Type-Options", "nosniff", "Previene MIME sniffing"),
        ("X-Frame-Options", "DENY", "Previene clickjacking"),
        ("Referrer-Policy", "strict-origin-when-cross-origin", "Limita referrer leak"),
        ("Permissions-Policy", "geolocation=(), microphone=(), camera=()", "Disabilita API browser sensibili"),
        ("Cross-Origin-Opener-Policy", "same-origin", "Isola contesto browsing"),
    ]
    story.append(_header_table(
        ["Header", "Valore", "Protezione"],
        headers,
        col_widths=[48*mm, 52*mm, CONTENT_W - 100*mm],
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("8.5 Audit Log", _st["H2"]))
    story.append(Paragraph(
        "Middleware HTTP intercetta tutte le azioni sensibili e scrive su tabella audit_logs. "
        "Azioni tracciate: document.upload, document.extract, document.delete, document.restore, "
        "document.permanent_delete, lab_test.confirm, report.medical_summary_download, "
        "settings.update, auth.login, auth.register, auth.logout. "
        "Ogni evento include: action, method, path, status_code, ip_address, user_agent, user_id, extra, timestamp.",
        _st["Body"],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 9. ACCESSIBILITA'
    # =====================================================================
    story.append(Paragraph("9. Accessibilita' (WCAG)", _st["H1"]))
    story.append(Paragraph(
        "E' stato eseguito un micro-step di accessibilita' in 7 tranche, tutte committate e verificate. "
        "L'obiettivo e' conformita' parziale WCAG 2.1 Level AA per uso personale/familiare.",
        _st["Body"],
    ))
    story.append(_header_table(
        ["Tranche", "Intervento", "Standard"],
        [
            ("A1", "Alert: role='alert'/'status', aria-live, aria-atomic. Button: aria-busy, spinner aria-hidden. Input: useId, aria-invalid, aria-describedby", "WCAG 4.1.3, 1.3.1"),
            ("A2", "Skip link globale '#main-content'. id='main-content' su tutti i landmark <main>", "WCAG 2.4.1, 1.3.1"),
            ("B1", "Tabelle: scope='col' su tutti gli <th>. aria-label su <table>. Colonna azioni sr-only", "WCAG 1.3.1, 4.1.2"),
            ("B2a", "Form login/register/documenti/trend/review: label+htmlFor+id associati. Review: aria-label dinamici per riga", "WCAG 1.3.1, 4.1.2"),
            ("B2b", "Form medicinali/terapie/promemoria/impostazioni: label+htmlFor+id associati", "WCAG 1.3.1, 4.1.2"),
            ("B3", "Tile trend: aria-pressed={selected === code}. type='button' esplicito", "WCAG 4.1.2"),
            ("B4", "Review: bottoni nativi type='button'. Alert inline con role/aria-live preservati post-refinement", "WCAG 4.1.2, 4.1.3"),
        ],
        col_widths=[18*mm, 95*mm, CONTENT_W - 113*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 10. REFINEMENT UI
    # =====================================================================
    story.append(Paragraph("10. Refinement UI", _st["H1"]))
    story.append(Paragraph(
        "Tutte le pagine principali sono state uniformate alla libreria componenti UI condivisa "
        "(Card, Alert, Button, Badge, EmptyState, Input). Nessuna classe inline residua per "
        "box/alert/badge/button. Focus ring visibile su tutti gli elementi interattivi.",
        _st["Body"],
    ))
    story.append(_header_table(
        ["Sprint", "Pagina", "Componenti Applicati"],
        [
            ("2A", "/notifications", "Card, Alert, Badge, EmptyState"),
            ("2B", "/medicines", "Card, Alert, Button, EmptyState, Input (nativo preservato)"),
            ("2B-bis", "/therapies", "Card, Alert, Button, Badge, EmptyState, stati PATCH preservati"),
            ("2C", "/trend", "Card, Alert, Button, Badge, EmptyState, grafico SVG preservato, ponte review preservato"),
            ("2D", "/documents/[id]/review", "Card, Alert, Button, Badge, EmptyState, logica estrazione/conferma preservata"),
        ],
        col_widths=[22*mm, 48*mm, CONTENT_W - 70*mm],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 11. REPORT PDF
    # =====================================================================
    story.append(Paragraph("11. Report PDF e Watermark", _st["H1"]))
    story.append(Paragraph("11.1 Specifica Tecnica Watermark", _st["H2"]))
    story.append(_kv_table([
        ("File modificato", "backend/app/services/medical_report.py"),
        ("Testo watermark", "VitaSync - Bozza personale - Verificare con medico"),
        ("Rotazione", "45 gradi centrato sulla pagina"),
        ("Font", "Helvetica-Bold 24pt"),
        ("Colore", "RGB(0.78, 0.78, 0.78) alpha 0.18"),
        ("Applicazione", "onFirstPage + onLaterPages callback"),
        ("Coordinate", "translate(A4[0]/2, A4[1]/2) + rotate(45) + drawCentredString(0,0)"),
        ("Test automatico", "PyMuPDF estrae testo watermark dal PDF generato in memoria"),
        ("Salvataggio su disco", "NO - PDF generato in BytesIO e ritornato come Response"),
    ]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("11.2 Contenuto Report PDF", _st["H2"]))
    story.append(Paragraph(
        "Il report include SOLO valori confermati dall'utente (confirmed_by_user=True) "
        "appartenenti a documenti ATTIVI (deleted_at IS NULL). "
        "Struttura: titolo, paziente, data generazione, gruppi di esame raggruppati per test_code, "
        "tabella per gruppo con colonne Data/Valore/Unita'/Range/Flag/Documento sorgente, "
        "disclaimer finale.",
        _st["Body"],
    ))
    story.append(PageBreak())

    # =====================================================================
    # 12. BACKUP / DR
    # =====================================================================
    story.append(Paragraph("12. Backup e Disaster Recovery", _st["H1"]))
    story.append(_header_table(
        ["Script", "Output", "Contenuto", "Frequenza Consigliata"],
        [
            ("scripts/backup-db.ps1", "backups/db/vitasync-db-*.dump", "pg_dump custom format completo", "Giornaliero"),
            ("scripts/backup-data.ps1", "backups/data/vitasync-data-*.zip", "Documenti + storage completo", "Giornaliero"),
            ("robocopy + Compress-Archive", "backups/vitasync-portal-*.zip", "Codice sorgente + config", "Ad ogni release"),
        ],
        col_widths=[38*mm, 48*mm, 48*mm, CONTENT_W - 134*mm],
    ))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "Restore drill validato: ripristino DB + storage + settings utente con verifica consistenza "
        "colonne Fernet e integrita' file. Tempo stimato restore completo: < 5 minuti.",
        _st["Body"],
    ))

    # =====================================================================
    # 13. STATO DATI
    # =====================================================================
    story.append(Paragraph("13. Stato Dati Attuale", _st["H1"]))
    stats = [
        ("Pazienti", str(_count(Patient))),
        ("Documenti totali", str(_count(Document))),
        ("Documenti attivi", str(_count_active_docs())),
        ("Lab test totali", str(_count(LabTest))),
        ("Lab test confermati", str(_count_confirmed())),
        ("Medicinali", str(_count(Medicine))),
        ("Terapie", str(_count(Therapy))),
        ("Promemoria", str(_count(Reminder))),
        ("Eventi audit", str(_count(AuditLog))),
    ]
    story.append(_kv_table(stats))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Snapshot generato il " + ts, _st["Small"]))

    # =====================================================================
    # 14. ROADMAP
    # =====================================================================
    story.append(PageBreak())
    story.append(Paragraph("14. Roadmap e Evoluzioni Future", _st["H1"]))
    story.append(_header_table(
        ["Sprint", "Feature", "Priorita'", "Stato"],
        [
            ("5.1", "Misure peso/altezza + BMI storico (tabella weight_measurements)", "Alta", "Pianificato"),
            ("5.2", "Alert deterministici su trend/range/terapie (senza AI)", "Alta", "Pianificato"),
            ("5.3", "Export Markdown/PDF completo per consulto medico o LLM esterno", "Media", "Pianificato"),
            ("5.4", "Hardening remote: HTTPS, invite-only, cookie secure, rate limit estesi", "Alta", "Pianificato"),
            ("5.5", "Test sicurezza: prompt injection, IDOR, privacy, penetration test", "Alta", "Pianificato"),
            ("6.0", "Health Summary Assistant: sintesi prudente dati confermati + contesto terapie", "Media", "Backlog"),
            ("6.1", "AI narrativa esterna opzionale (LLM locale, export pseudonimizzato)", "Bassa", "Backlog"),
        ],
        col_widths=[18*mm, 82*mm, 22*mm, CONTENT_W - 122*mm],
    ))

    # =====================================================================
    # 15. GLOSSARIO
    # =====================================================================
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("15. Glossario", _st["H1"]))
    glossary = [
        ("LabTest", "Singolo valore di laboratorio estratto da un referto e associato a un documento"),
        ("Bozza", "Valore estratto ma non ancora confermato dall'utente (confirmed_by_user=False)"),
        ("Confermato", "Valore verificato e approvato dall'utente (confirmed_by_user=True)"),
        ("Soft Delete", "Documento marcato come eliminato (deleted_at impostato) ma recuperabile dal cestino"),
        ("Permanent Delete", "Eliminazione definitiva del record DB + file dallo storage"),
        ("Watermark", "Testo diagonale semi-trasparente applicato ad ogni pagina del PDF report"),
        ("Fernet", "Schema di cifratura simmetrica AES-128-CBC + HMAC usato per password SMTP"),
        ("Magic Bytes", "Sequenza di byte iniziale di un file usata per rilevarne il tipo reale"),
        ("OCR", "Optical Character Recognition - estrazione testo da immagini rasterizzate"),
        ("Flag", "Indicatore calcolato automaticamente: normal/above_range/below_range/critical/unknown"),
        ("Invite Code", "Codice monouso richiesto per la registrazione, abilita accesso familiare chiuso"),
        ("Audit Log", "Registro immutabile di tutte le azioni sensibili con timestamp e contesto"),
    ]
    story.append(_header_table(
        ["Termine", "Definizione"],
        glossary,
        col_widths=[35*mm, CONTENT_W - 35*mm],
    ))

    # =====================================================================
    # 16. DISCLAIMER
    # =====================================================================
    story.append(PageBreak())
    story.append(Paragraph("16. Disclaimer e Limiti", _st["H1"]))
    story.append(Paragraph(
        "<b>Questo software e questa documentazione non costituiscono parere medico.</b> "
        "VitaSync Portal e' uno strumento di organizzazione personale/familiare. "
        "I valori estratti vanno sempre verificati dall'utente sui referti originali. "
        "Il sistema non formula diagnosi, non valuta l'efficacia terapeutica e non stabilisce "
        "rapporti di causa-effetto tra farmaci e valori di laboratorio. "
        "In caso di sintomi acuti o gravi, contattare immediatamente i servizi di emergenza.",
        _st["Body"],
    ))
    story.append(Spacer(1, 6*mm))
    story.append(_hr())
    story.append(Paragraph(
        "Documento generato automaticamente il " + ts + " da VitaSync Portal backend. "
        "La presente specifica riflette lo stato del codice al momento della generazione.",
        _st["Footer"],
    ))

    # BUILD
    doc.build(story, onFirstPage=_add_watermark, onLaterPages=_add_watermark)
    return buffer.getvalue()


def main():
    out_dir = Path(settings.local_storage_path).resolve() / "_docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = out_dir / ("vitasync-spec-funzionale-" + ts + ".pdf")
    pdf_bytes = build_pdf()
    out_file.write_bytes(pdf_bytes)
    print("PDF generato: " + str(out_file))
    print("Dimensione: " + str(len(pdf_bytes)) + " bytes")


if __name__ == "__main__":
    main()