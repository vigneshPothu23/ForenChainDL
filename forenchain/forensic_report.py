from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F5597")
PALE = colors.HexColor("#EEF3F8")
LIGHT = colors.HexColor("#F8FAFC")
GREY = colors.HexColor("#64748B")
BORDER = colors.HexColor("#CBD5E1")
DARK = colors.HexColor("#1E293B")


def _text(value):
    return escape(str(value if value not in (None, "") else "Not available"))


def _hash_paragraph(value, style):
    """Wrap a hash using line breaks only; never insert hash characters."""
    value = str(value if value else "Not available")
    if value == "Not available":
        return Paragraph(_text(value), style)
    chunks = [escape(value[i:i + 32]) for i in range(0, len(value), 32)]
    return Paragraph("<br/>".join(chunks), style)


def _draw_page(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4

    # Restrained institutional header.
    canvas.setFillColor(NAVY)
    canvas.rect(0, page_height - 5 * mm, page_width, 5 * mm, fill=1, stroke=0)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(17 * mm, 15 * mm, page_width - 17 * mm, 15 * mm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(17 * mm, 9 * mm, "FORENCHAIN-DL | Forensic examination record")
    canvas.drawRightString(page_width - 17 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_forensic_report_pdf(metadata, original, heatmap):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=13 * mm,
        bottomMargin=21 * mm,
        title="Digital Evidence Forensic Examination Report",
        author="ForenChain-DL",
        subject=f"Evidence {metadata.get('evidence_id', 'Not available')}",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Brand",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        alignment=TA_CENTER,
        textColor=NAVY,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SubtitleCustom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=DARK,
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SectionCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=NAVY,
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=DARK,
        splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="HashCustom",
        parent=styles["BodyText"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=DARK,
    ))
    styles.add(ParagraphStyle(
        name="LabelCustom",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=DARK,
    ))
    styles.add(ParagraphStyle(
        name="CaptionCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=GREY,
    ))
    styles.add(ParagraphStyle(
        name="NoticeCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=DARK,
    ))

    story = []

    # PAGE 1 — Report identification and recorded findings.
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("FORENCHAIN-DL", styles["Brand"]))
    story.append(Paragraph(
        "DIGITAL EVIDENCE FORENSIC EXAMINATION REPORT",
        styles["SubtitleCustom"],
    ))
    story.append(Paragraph(
        "PROTOTYPE REPORT — FOR EXAMINER REVIEW",
        ParagraphStyle(
            "ClassificationCustom",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=BLUE,
            spaceAfter=4 * mm,
        ),
    ))

    identification = Table(
        [[
            Paragraph("<b>CASE ID</b><br/>" + _text(metadata.get("case_id")),
                      styles["BodyCustom"]),
            Paragraph("<b>EVIDENCE ID</b><br/>" + _text(metadata.get("evidence_id")),
                      styles["BodyCustom"]),
        ], [
            Paragraph("<b>ANALYSIS ID</b><br/>" + _text(metadata.get("analysis_id")),
                      styles["BodyCustom"]),
            Paragraph("<b>REPORT TYPE</b><br/>AI-assisted image examination",
                      styles["BodyCustom"]),
        ]],
        colWidths=[86 * mm, 86 * mm],
    )
    identification.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([identification, Spacer(1, 3 * mm)])

    story.append(Paragraph("1. Examination Summary", styles["SectionCustom"]))
    story.append(Paragraph(
        "This document records the registered image details, a SHA-256 "
        "integrity comparison, and the output from an AI-assisted screening "
        "run. It is a technical record for examiner review, not a standalone "
        "determination of authenticity or manipulation.",
        styles["BodyCustom"],
    ))

    story.append(Paragraph("2. Evidence Identification and Integrity",
                           styles["SectionCustom"]))

    rows = [[
        Paragraph("<b>Recorded field</b>", styles["BodyCustom"]),
        Paragraph("<b>Value</b>", styles["BodyCustom"]),
    ]]

    fields = [
        ("original_filename", "Original filename", False),
        ("registered_sha256", "Registered SHA-256", True),
        ("analyzed_sha256", "Analyzed file SHA-256", True),
        ("integrity_status", "Integrity verification status", False),
        ("integrity_checked_at", "Verification time (UTC)", False),
        ("examiner_username", "Examiner account", False),
        ("examiner_user_id", "Examiner user ID", False),
    ]

    for key, label, is_hash in fields:
        value = metadata.get(key, "Not available")
        value_paragraph = (
            _hash_paragraph(value, styles["HashCustom"])
            if is_hash else Paragraph(_text(value), styles["BodyCustom"])
        )
        rows.append([
            Paragraph(_text(label), styles["LabelCustom"]),
            value_paragraph,
        ])

    evidence_table = Table(
        rows, colWidths=[52 * mm, 120 * mm], repeatRows=1
    )
    evidence_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(evidence_table)

    story.append(Paragraph("3. AI Screening Record", styles["SectionCustom"]))
    ai_rows = [
        ("Model", metadata.get("model_name")),
        ("Model response score", metadata.get("model_response_score")),
        ("Inference device", metadata.get("inference_device")),
        ("Analysis timestamp (UTC)", metadata.get("analyzed_at")),
    ]
    ai_table = Table(
        [[Paragraph("<b>" + _text(label) + "</b>", styles["BodyCustom"]),
          Paragraph(_text(value), styles["BodyCustom"])]
         for label, value in ai_rows],
        colWidths=[52 * mm, 120 * mm],
    )
    ai_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([ai_table, Spacer(1, 3 * mm)])


    # PAGE 2 — Visual exhibits and interpretation.
    story.append(PageBreak())
    story.append(Paragraph("4. Visual Examination Exhibits",
                           styles["SectionCustom"]))
    story.append(Paragraph(
        "Exhibit A shows the registered image used for screening. Exhibit B "
        "shows the model's normalized localization response visualization.",
        styles["BodyCustom"],
    ))
    story.append(Spacer(1, 4 * mm))

    original_buffer = BytesIO()
    original.convert("RGB").save(original_buffer, format="PNG")
    original_buffer.seek(0)

    heatmap_buffer = BytesIO()
    heatmap.convert("RGB").save(heatmap_buffer, format="PNG")
    heatmap_buffer.seek(0)

    original_image = Image(
        original_buffer, width=82 * mm, height=90 * mm,
        kind="proportional",
    )
    heatmap_image = Image(
        heatmap_buffer, width=82 * mm, height=90 * mm,
        kind="proportional",
    )

    exhibits = Table(
        [[original_image, heatmap_image],
         [Paragraph("<b>EXHIBIT A</b><br/>Registered evidence image",
                    styles["CaptionCustom"]),
          Paragraph("<b>EXHIBIT B</b><br/>Normalized AI response heatmap",
                    styles["CaptionCustom"])]],
        colWidths=[86 * mm, 86 * mm],
        hAlign="CENTER",
    )
    exhibits.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([exhibits, Spacer(1, 5 * mm)])

    story.append(Paragraph("5. Interpretation and Limitations",
                           styles["SectionCustom"]))
    story.append(Paragraph(
        "A matching SHA-256 value indicates that the compared file bytes "
        "match the registered bytes. A mismatch indicates a byte-level "
        "difference but does not, by itself, establish malicious alteration. "
        "Re-encoding, compression, or conversion may change a file hash. "
        "The normalized heatmap is not a verified tampering mask. Findings "
        "require independent examiner review and corroboration.",
        styles["BodyCustom"],
    ))

    story.append(Paragraph("6. Examiner Review", styles["SectionCustom"]))
    conclusion = _text(metadata.get("examiner_conclusion", "Not recorded"))
    notes = _text(metadata.get("examiner_notes", "No findings recorded."))
    story.append(Paragraph(
        f"<b>Examiner conclusion:</b> {conclusion}<br/>"
        f"<b>Findings and observations:</b> {notes}<br/>"
        "This report does not replace validated forensic procedures "
        "or a signed expert opinion.",
        styles["BodyCustom"],
    ))
    story.append(Spacer(1, 5 * mm))

    signoff = Table(
        [[
            Paragraph("<b>Examiner signature</b><br/><br/>"
                      "________________________________", styles["BodyCustom"]),
            Paragraph("<b>Date</b><br/><br/>"
                      "________________________________", styles["BodyCustom"]),
        ]],
        colWidths=[86 * mm, 86 * mm],
    )
    signoff.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(signoff)

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return output.getvalue()
