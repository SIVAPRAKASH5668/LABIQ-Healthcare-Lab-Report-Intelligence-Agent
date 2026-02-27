#!/usr/bin/env python3
"""
Generate realistic multi-patient lab report PDFs
7 patients × 5 visits = 35 PDFs
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os

# Output folder
OUTPUT_DIR = "/home/sivaprakash/Downloads/healthcare/sample"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ───────────────────────────────
# PATIENT DATABASE
# ───────────────────────────────

PATIENTS = {


    "PAT004": {
        "name": "Ahmed Khan",
        "dob": "11.02.1962",
        "gender": "Male",
        "story": "kidney_disease",
    },

    "PAT005": {
        "name": "Fatima Noor",
        "dob": "05.09.1992",
        "gender": "Female",
        "story": "anemia",
    },

    "PAT006": {
        "name": "Ravi Kumar",
        "dob": "18.07.1978",
        "gender": "Male",
        "story": "liver_issue",
    },

    "PAT007": {
        "name": "Neha Gupta",
        "dob": "12.12.1990",
        "gender": "Female",
        "story": "thyroid",
    },
}


# ───────────────────────────────
# VISITS
# ───────────────────────────────

VISIT_DATES = [
    "27.04.2024",
    "15.07.2024",
    "03.10.2024",
    "18.01.2025",
    "05.04.2025",
]


# ───────────────────────────────
# VALUE GENERATOR
# ───────────────────────────────

def get_values(story, i):

    if story == "diabetic_lipid":

        return {
            "Glucose fasting": (120 - i*8, 70, 99, "mg/dl"),
            "Cholesterol total": (221 - i*12, 100, 200, "mg/dl"),
            "Triglycerides": (1315 - i*180, 0, 150, "mg/dl"),
            "HDL Cholesterol": (22 + i*5, 50, 100, "mg/dl"),
            "LDL Cholesterol": (36 + i*3, 0, 100, "mg/dl"),
            "Albumin": (4.5, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (9 + i, 6, 20, "mg/dl"),
            "Creatinine": (0.7 + i*0.05, 0.4, 0.9, "mg/dl"),
            "Total Protein": (7.1, 6.4, 8.3, "g/dl"),
            "HbA1c": (3.8 + i*0.4, 2.9, 5.6, "%"),
        }

    elif story == "cardiac_risk":

        return {
            "Glucose fasting": (95 + i*6, 70, 99, "mg/dl"),
            "Cholesterol total": (190 + i*15, 100, 200, "mg/dl"),
            "Triglycerides": (180 + i*40, 0, 150, "mg/dl"),
            "HDL Cholesterol": (45 - i*3, 50, 100, "mg/dl"),
            "LDL Cholesterol": (110 + i*12, 0, 100, "mg/dl"),
            "Albumin": (4.2 - i*0.1, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (14 + i*2, 6, 20, "mg/dl"),
            "Creatinine": (0.9 + i*0.15, 0.4, 0.9, "mg/dl"),
            "Total Protein": (7.0, 6.4, 8.3, "g/dl"),
            "HbA1c": (5.2 + i*0.3, 2.9, 5.6, "%"),
        }

    elif story == "kidney_disease":

        return {
            "Glucose fasting": (90 + i*2, 70, 99, "mg/dl"),
            "Cholesterol total": (180, 100, 200, "mg/dl"),
            "Triglycerides": (140, 0, 150, "mg/dl"),
            "HDL Cholesterol": (55, 50, 100, "mg/dl"),
            "LDL Cholesterol": (95, 0, 100, "mg/dl"),
            "Albumin": (4.0 - i*0.3, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (18 + i*5, 6, 20, "mg/dl"),
            "Creatinine": (1.1 + i*0.4, 0.4, 0.9, "mg/dl"),
            "Total Protein": (6.8 - i*0.2, 6.4, 8.3, "g/dl"),
            "HbA1c": (5.3, 2.9, 5.6, "%"),
        }

    elif story == "anemia":

        return {
            "Glucose fasting": (85, 70, 99, "mg/dl"),
            "Cholesterol total": (165, 100, 200, "mg/dl"),
            "Triglycerides": (100, 0, 150, "mg/dl"),
            "HDL Cholesterol": (60, 50, 100, "mg/dl"),
            "LDL Cholesterol": (80, 0, 100, "mg/dl"),
            "Albumin": (3.4 + i*0.2, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (10, 6, 20, "mg/dl"),
            "Creatinine": (0.6, 0.4, 0.9, "mg/dl"),
            "Total Protein": (6.2 + i*0.3, 6.4, 8.3, "g/dl"),
            "HbA1c": (4.8, 2.9, 5.6, "%"),
        }

    elif story == "liver_issue":

        return {
            "Glucose fasting": (92, 70, 99, "mg/dl"),
            "Cholesterol total": (210 - i*5, 100, 200, "mg/dl"),
            "Triglycerides": (200 - i*15, 0, 150, "mg/dl"),
            "HDL Cholesterol": (48 + i*2, 50, 100, "mg/dl"),
            "LDL Cholesterol": (130 - i*10, 0, 100, "mg/dl"),
            "Albumin": (3.2 + i*0.3, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (11, 6, 20, "mg/dl"),
            "Creatinine": (0.8, 0.4, 0.9, "mg/dl"),
            "Total Protein": (6.0 + i*0.4, 6.4, 8.3, "g/dl"),
            "HbA1c": (5.1, 2.9, 5.6, "%"),
        }

    elif story == "thyroid":

        return {
            "Glucose fasting": (89, 70, 99, "mg/dl"),
            "Cholesterol total": (195 - i*4, 100, 200, "mg/dl"),
            "Triglycerides": (135 - i*5, 0, 150, "mg/dl"),
            "HDL Cholesterol": (58, 50, 100, "mg/dl"),
            "LDL Cholesterol": (105 - i*3, 0, 100, "mg/dl"),
            "Albumin": (4.4, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (12, 6, 20, "mg/dl"),
            "Creatinine": (0.7, 0.4, 0.9, "mg/dl"),
            "Total Protein": (7.0, 6.4, 8.3, "g/dl"),
            "HbA1c": (5.0, 2.9, 5.6, "%"),
        }

    else:

        return {
            "Glucose fasting": (88 + i*3, 70, 99, "mg/dl"),
            "Cholesterol total": (175 + i*5, 100, 200, "mg/dl"),
            "Triglycerides": (110 + i*8, 0, 150, "mg/dl"),
            "HDL Cholesterol": (62 - i*2, 50, 100, "mg/dl"),
            "LDL Cholesterol": (88 + i*4, 0, 100, "mg/dl"),
            "Albumin": (4.6, 3.5, 5.0, "g/dl"),
            "Urea Nitrogen": (12, 6, 20, "mg/dl"),
            "Creatinine": (0.75, 0.4, 0.9, "mg/dl"),
            "Total Protein": (7.3, 6.4, 8.3, "g/dl"),
            "HbA1c": (5.0 + i*0.1, 2.9, 5.6, "%"),
        }


# ───────────────────────────────
# PDF GENERATOR
# ───────────────────────────────

def generate_pdf(pid, patient, date, visit):

    values = get_values(patient["story"], visit)

    filename = f"{OUTPUT_DIR}/{pid}_{date.replace('.','-')}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4)

    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("Medical Laboratory Report", styles['Title']))
    story.append(Spacer(1,10))

    story.append(Paragraph(f"Patient: {patient['name']}", styles['Normal']))
    story.append(Paragraph(f"Patient ID: {pid}", styles['Normal']))
    story.append(Paragraph(f"DOB: {patient['dob']}", styles['Normal']))
    story.append(Paragraph(f"Gender: {patient['gender']}", styles['Normal']))
    story.append(Paragraph(f"Date: {date}", styles['Normal']))

    story.append(Spacer(1,20))


    data=[["Test","Result","Flag","Unit","Range"]]

    for k,(v,minv,maxv,u) in values.items():

        v=round(v,1)

        flag=""

        if v>maxv:
            flag="HIGH"
        elif v<minv:
            flag="LOW"

        data.append([k,str(v),flag,u,f"{minv}-{maxv}"])


    table=Table(data)

    table.setStyle(TableStyle([

        ('GRID',(0,0),(-1,-1),1,colors.black),

        ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),

        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')

    ]))

    story.append(table)

    doc.build(story)

    return filename


# ───────────────────────────────
# MAIN
# ───────────────────────────────

if __name__=="__main__":

    total=0

    for pid,p in PATIENTS.items():

        for i,d in enumerate(VISIT_DATES):

            path=generate_pdf(pid,p,d,i)

            print("Generated:",path)

            total+=1


    print("\nTOTAL FILES:",total)