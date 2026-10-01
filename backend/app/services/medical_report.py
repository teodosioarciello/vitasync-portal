"""
Sprint 3 - Report PDF per consulto medico.

Genera un riepilogo stampabile dei valori di laboratorio CONFERMATI
appartenenti a documenti ATTIVI (non nel cestino).

Questo modulo:
- NON salva il PDF su disco;
- NON invia il PDF via email;
- NON include valori non confermati;
- NON include documenti nel cestino o eliminati definitivamente.
"""

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models import Document, LabTest, Patient


def _fmt_value(value) -> str:
    if value is None:
        return "-"

    if isinstance(value, Decimal):
        return format(value.normalize(), "f")

    return str(value)


def _fmt_date(value) -> str:
    if value is None:
        return "-"

    return value.strftime("%d/%m/%Y")


def _ref_range(lab: LabTest) -> str:
    if lab.reference_min is None and lab.reference_max is None:
        return ""

    return f"{_fmt_value(lab.reference_min)} - {_fmt_value(lab.reference_max)}"


def collect_report_data(db: Session, patient: Patient) -> dict:
    """
    Raccoglie i valori confermati da documenti attivi, raggruppati per test_code.
    """
    rows = (
        db.query(LabTest, Document)
        .join(Document, Document.id == LabTest.document_id)
        .filter(
            LabTest.patient_id == patient.id,
            LabTest.confirmed_by_user.is_(True),
            Document.deleted_at.is_(None),
        )
        .order_by(
            LabTest.test_code.asc(),
            LabTest.extracted_at.asc(),
            LabTest.created_at.asc(),
        )
        .all()
    )

    groups: dict[str, dict] = {}
    order: list[str] = []

    for lab, document in rows:
        code = lab.test_code or "unknown"

        if code not in groups:
            groups[code] = {
                "test_code": code,
                "test_name": lab.test_name_normalized or lab.test_name_original or code,
                "unit": lab.unit,
                "points": [],
            }
            order.append(code)

        when = lab.extracted_at or lab.created_at

        groups[code]["points"].append(
            {
                "date": _fmt_date(when),
                "value": _fmt_value(lab.value_numeric),
                "unit": lab.unit or "",
                "reference": lab.reference_text or _ref_range(lab),
                "flag": lab.flag or "",
                "document_title": document.title if document else "",
            }
        )

    return {
        "patient_name": patient.display_name,
        "patient_id": str(patient.id),
        "generated_at": _fmt_date(datetime.now(timezone.utc)),
        "groups": [groups[code] for code in order],
        "totals": {
            "groups": len(order),
            "rows": len(rows),
        },
    }


def build_pdf_bytes(data: dict) -> bytes:
    """
    Costruisce il PDF in memoria e ritorna i byte.
    Nulla viene scritto su disco.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="VitaSync Portal - Riepilogo esami di laboratorio",
        author="VitaSync Portal",
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            "VitaSync Portal - Riepilogo esami di laboratorio",
            styles["Title"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(f"Paziente: <b>{escape(data['patient_name'])}</b>", styles["Normal"])
    )
    story.append(
        Paragraph(
            f"Generato il: {escape(data['generated_at'])}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            "Gruppi di esame: "
            f"{data['totals']['groups']} - Valori confermati: {data['totals']['rows']}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    if not data["groups"]:
        story.append(
            Paragraph(
                "Nessun valore di laboratorio confermato disponibile.",
                styles["Normal"],
            )
        )
    else:
        for group in data["groups"]:
            story.append(
                Paragraph(
                    f"<b>{escape(group['test_name'])}</b> ({escape(group['test_code'])})",
                    styles["Heading3"],
                )
            )
            story.append(Spacer(1, 2 * mm))

            table_data = [
                ["Data", "Valore", "Unita'", "Range riferimento", "Flag", "Documento sorgente"]
            ]

            for point in group["points"]:
                table_data.append(
                    [
                        point["date"] or "-",
                        point["value"],
                        point["unit"] or "-",
                        point["reference"] or "-",
                        point["flag"] or "-",
                        point["document_title"] or "-",
                    ]
                )

            table = Table(
                table_data,
                repeatRows=1,
                colWidths=[34 * mm, 20 * mm, 14 * mm, 32 * mm, 16 * mm, 64 * mm],
            )
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f8fafc")],
                        ),
                    ]
                )
            )

            story.append(table)
            story.append(Spacer(1, 6 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Documento generato automaticamente da VitaSync Portal a partire dai soli "
            "valori confermati dall'utente e dai documenti non eliminati. Questo "
            "riepilogo e' uno strumento organizzativo: non formula diagnosi, non "
            "sostituisce il parere medico e non deve essere usato come unica fonte "
            "clinica.",
            styles["Normal"],
        )
    )

    doc.build(story)
    return buffer.getvalue()