#!/usr/bin/env python3
"""
Generate realistic multi-patient, multi-date lab report PDFs
3 patients × 5 dates = 15 PDFs with believable value progressions
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os, random

OUTPUT_DIR = "/home/sivaprakash/Downloads/healthcare/sample"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Patient profiles ──────────────────────────────────────────────────────────
PATIENTS = {
    "PAT001": {
        "name": "Sarah Al-Hassan",
        "dob": "01.01.1973", "gender": "Female",
        "story": "diabetic_lipid",   # starts bad, improves with treatment
    },
    "PAT002": {
        "name": "Mohammed Al-Farsi",
        "dob": "15.06.1958", "gender": "Male",
        "story": "cardiac_risk",     # worsening cardiac markers
    },
    "PAT003": {
        "name": "Priya Sharma",
        "dob": "22.03.1985", "gender": "Female",
        "story": "healthy_checkup",  # mostly normal, minor glucose issue
    },
}

# ── Test dates (5 visits over ~18 months) ────────────────────────────────────
VISIT_DATES = [
    "27.04.2024",
    "15.07.2024",
    "03.10.2024",
    "18.01.2025",
    "05.04.2025",
]

# ── Value progressions per story ─────────────────────────────────────────────
def get_values(story, visit_idx):
    """Return dict of test_name → (value, ref_min, ref_max, unit)"""
    i = visit_idx  # 0-4

    if story == "diabetic_lipid":
        # Starts critical, improves with medication
        return {
            "Glucose fasting (PHO)":           (120 - i*8,        70,  99,  "mg/dl"),
            "Cholesterol, total (PHO)":        (221 - i*12,       100, 200, "mg/dl"),
            "Triglycerides (PHO)":             (1315 - i*180,     0,   150, "mg/dl"),
            "HDL Cholesterol, direct (PHO)":   (22.5 + i*5,       50,  100, "mg/dl"),
            "LDL Cholesterol, direct (PHO)":   (36 + i*3,         0,   100, "mg/dl"),
            "Albumin (PHO)":                   (4.5,              3.5, 5.0, "g/dl"),
            "Urea Nitrogen (PHO)":             (9 + i,            6,   20,  "mg/dl"),
            "Creatinine (PHO)":                (0.7 + i*0.05,     0.4, 0.9, "mg/dl"),
            "Total Protein (PHO)":             (7.1,              6.4, 8.3, "g/dl"),
            "Hb A1c (TURB)":                   (3.8 + i*0.4,      2.9, 5.6, "%"),
        }
    elif story == "cardiac_risk":
        # Worsening over time
        return {
            "Glucose fasting (PHO)":           (95 + i*6,         70,  99,  "mg/dl"),
            "Cholesterol, total (PHO)":        (190 + i*15,       100, 200, "mg/dl"),
            "Triglycerides (PHO)":             (180 + i*40,       0,   150, "mg/dl"),
            "HDL Cholesterol, direct (PHO)":   (45 - i*3,         50,  100, "mg/dl"),
            "LDL Cholesterol, direct (PHO)":   (110 + i*12,       0,   100, "mg/dl"),
            "Albumin (PHO)":                   (4.2 - i*0.1,      3.5, 5.0, "g/dl"),
            "Urea Nitrogen (PHO)":             (14 + i*2,         6,   20,  "mg/dl"),
            "Creatinine (PHO)":                (0.9 + i*0.15,     0.4, 0.9, "mg/dl"),
            "Total Protein (PHO)":             (7.0,              6.4, 8.3, "g/dl"),
            "Hb A1c (TURB)":                   (5.2 + i*0.3,      2.9, 5.6, "%"),
        }
    else:  # healthy_checkup
        return {
            "Glucose fasting (PHO)":           (88 + i*3,         70,  99,  "mg/dl"),
            "Cholesterol, total (PHO)":        (175 + i*5,        100, 200, "mg/dl"),
            "Triglycerides (PHO)":             (110 + i*8,        0,   150, "mg/dl"),
            "HDL Cholesterol, direct (PHO)":   (62 - i*2,         50,  100, "mg/dl"),
            "LDL Cholesterol, direct (PHO)":   (88 + i*4,         0,   100, "mg/dl"),
            "Albumin (PHO)":                   (4.6,              3.5, 5.0, "g/dl"),
            "Urea Nitrogen (PHO)":             (12,               6,   20,  "mg/dl"),
            "Creatinine (PHO)":                (0.75,             0.4, 0.9, "mg/dl"),
            "Total Protein (PHO)":             (7.3,              6.4, 8.3, "g/dl"),
            "Hb A1c (TURB)":                   (5.0 + i*0.1,      2.9, 5.6, "%"),
        }

# ── PDF generation ────────────────────────────────────────────────────────────
def generate_pdf(patient_id, patient, visit_date, visit_idx):
    values = get_values(patient["story"], visit_idx)
    filename = f"{OUTPUT_DIR}/{patient_id}_{visit_date.replace('.', '-')}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story  = []

    # Header
    header_style = ParagraphStyle("header", fontSize=13, fontName="Helvetica-Bold",
                                  spaceAfter=2*mm)
    sub_style    = ParagraphStyle("sub", fontSize=9, fontName="Helvetica",
                                  spaceAfter=1*mm, textColor=colors.grey)
    normal_style = ParagraphStyle("norm", fontSize=9, fontName="Helvetica",
                                  spaceAfter=1*mm)

    story.append(Paragraph("Freiburg Medical Laboratory Middle East (L.L.C.)", header_style))
    story.append(Paragraph("P.O. Box: 3068, Dubai - UAE | Tel: 04 396 2227 | info@fml-dubai.com", sub_style))
    story.append(Spacer(1, 4*mm))

    # Patient info table
    info_data = [
        ["Patient Name:", patient["name"], "Report Date:", visit_date],
        ["Date of Birth:", patient["dob"], "Gender:", patient["gender"]],
        ["Patient ID:", patient_id, "Sampling Date:", visit_date],
    ]
    info_table = Table(info_data, colWidths=[38*mm, 65*mm, 35*mm, 42*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))

    # Results table
    story.append(Paragraph("Proteins / Metabolites (Serum)", 
                            ParagraphStyle("section", fontSize=10, fontName="Helvetica-Bold",
                                           spaceAfter=2*mm, spaceBefore=3*mm)))

    header_row = ["Analysis", "Result", "Flag", "Units", "Reference Range"]
    rows = [header_row]

    for test_name, (value, ref_min, ref_max, unit) in values.items():
        value = round(value, 1)
        flag  = ""
        if value > ref_max:
            flag = "high"
        elif value < ref_min:
            flag = "low"
        ref_str = f"{ref_min} - {ref_max}" if ref_min > 0 else f"< {ref_max}"
        rows.append([test_name, str(value), flag, unit, ref_str])

    result_table = Table(rows, colWidths=[75*mm, 22*mm, 15*mm, 20*mm, 40*mm])
    style = TableStyle([
        ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("BACKGROUND",   (0,0), (-1,0),  colors.HexColor("#2E4057")),
        ("TEXTCOLOR",    (0,0), (-1,0),  colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",         (0,0), (-1,-1), 0.3, colors.HexColor("#CCCCCC")),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ("TOPPADDING",   (0,0), (-1,-1), 3),
    ])
    # Highlight abnormal values
    for row_idx, (test_name, (value, ref_min, ref_max, unit)) in enumerate(values.items(), 1):
        value = round(value, 1)
        if value > ref_max:
            style.add("TEXTCOLOR", (1, row_idx), (2, row_idx), colors.HexColor("#CC0000"))
            style.add("FONTNAME",  (1, row_idx), (2, row_idx), "Helvetica-Bold")
        elif value < ref_min:
            style.add("TEXTCOLOR", (1, row_idx), (2, row_idx), colors.HexColor("#0000CC"))
            style.add("FONTNAME",  (1, row_idx), (2, row_idx), "Helvetica-Bold")

    result_table.setStyle(style)
    story.append(result_table)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        "Note: Our reference values are adjusted to age and gender. "
        "Daily internal Quality Control within the required range (ISO 15189).",
        sub_style))

    doc.build(story)
    return filename

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    generated = []
    for patient_id, patient in PATIENTS.items():
        for visit_idx, visit_date in enumerate(VISIT_DATES):
            path = generate_pdf(patient_id, patient, visit_date, visit_idx)
            generated.append(path)
            print(f"✅ {path}")

    print(f"\n🎉 Generated {len(generated)} PDFs in {OUTPUT_DIR}/")
    print("\nUpload order per patient:")
    for pid in PATIENTS:
        print(f"\n  {pid}:")
        for d in VISIT_DATES:
            print(f"    {OUTPUT_DIR}/{pid}_{d.replace('.', '-')}.pdf")