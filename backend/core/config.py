# backend/core/config.py
import os
import re
from dotenv import load_dotenv
from typing import Optional
load_dotenv()

class Settings:

    APP_NAME:    str = os.getenv("APP_NAME", "LabIQ")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    LOG_LEVEL:   str = os.getenv("LOG_LEVEL", "INFO")

    ELASTIC_ENDPOINT: str           = os.getenv("ELASTIC_ENDPOINT", "")
    ELASTIC_API_KEY:  str           = os.getenv("ELASTIC_API_KEY", "")
    OPENAI_API_KEY:   Optional[str] = os.getenv("OPENAI_API_KEY")

    LAB_RESULTS_INDEX:    str = "lab-results"
    KNOWLEDGE_BASE_INDEX: str = "knowledge-base"

    # ── Risk vector definition ─────────────────────────────────
    # 8 biomarkers matched to what your PDFs actually contain.
    # Uses fuzzy name matching — "(PHO)", "(TURB)" suffixes are ignored.
    # Each entry: (canonical_name, keywords_to_match, clinical_low, clinical_high)
    RISK_VECTOR_FIELDS = [
        ("Triglycerides", ["triglyceride"],               0.0,   500.0),
        ("HDL",           ["hdl"],                       20.0,   100.0),
        ("LDL",           ["ldl"],                        0.0,   200.0),
        ("Cholesterol",   ["cholesterol, total",
                           "total cholesterol"],         100.0,  300.0),
        ("Glucose",       ["glucose"],                    50.0,  400.0),
        ("HbA1c",         ["hb a1c", "hba1c", "a1c"],    2.0,    10.0),
        ("Creatinine",    ["creatinine"],                  0.4,    5.0),
        ("Albumin",       ["albumin"],                     2.0,    5.5),
    ]

    # ── Risk scoring weights ───────────────────────────────────
    RISK_WEIGHTS = {
        "Potassium":       25,
        "Sodium":          20,
        "Creatinine":      18,
        "Glucose":         15,
        "Hemoglobin":      12,
        "WBC":             10,
        "Calcium":         10,
        "Platelets":        8,
        "Hb A1c":           6,
        "TSH":              7,
        "Triglycerides":   15,
        "HDL Cholesterol": 10,
        "LDL Cholesterol":  8,
        "Cholesterol":      6,
        "ALT":              5,
        "AST":              5,
        "Bilirubin":        5,
    }

    REFERENCE_RANGES = {
        # ── Glucose ──────────────────────────────────────────
        "Glucose":                          {"min": 70,  "max": 100, "unit": "mg/dL", "critical_high": 400, "critical_low": 50},
        "Glucose Fasting":                  {"min": 70,  "max": 100, "unit": "mg/dL", "critical_high": 400, "critical_low": 50},
        "Glucose fasting (PHO)":            {"min": 70,  "max": 99,  "unit": "mg/dL", "critical_high": 400, "critical_low": 50},
        "Glucose (PP)":                     {"min": 70,  "max": 140, "unit": "mg/dL", "critical_high": 400, "critical_low": 50},
        "Glucose Fasting (Hexokinase)":     {"min": 70,  "max": 100, "unit": "mg/dL", "critical_high": 400, "critical_low": 50},

        # ── Lipids ───────────────────────────────────────────
        "Cholesterol":                      {"min": 125, "max": 200, "unit": "mg/dL", "critical_high": 300, "critical_low": None},
        "Cholesterol, total":               {"min": 125, "max": 200, "unit": "mg/dL", "critical_high": 300, "critical_low": None},
        "Cholesterol, total (PHO)":         {"min": 100, "max": 200, "unit": "mg/dL", "critical_high": 300, "critical_low": None},
        "Total Cholesterol":                {"min": 125, "max": 200, "unit": "mg/dL", "critical_high": 300, "critical_low": None},
        "Triglycerides":                    {"min": 0,   "max": 150, "unit": "mg/dL", "critical_high": 500, "critical_low": None},
        "Triglycerides (PHO)":              {"min": 0,   "max": 150, "unit": "mg/dL", "critical_high": 500, "critical_low": None},
        "HDL Cholesterol":                  {"min": 40,  "max": 60,  "unit": "mg/dL", "critical_high": None, "critical_low": 30},
        "HDL Cholesterol, direct":          {"min": 50,  "max": 80,  "unit": "mg/dL", "critical_high": None, "critical_low": 25},
        "HDL Cholesterol, direct (PHO)":    {"min": 50,  "max": 80,  "unit": "mg/dL", "critical_high": None, "critical_low": 25},
        "HDL":                              {"min": 40,  "max": 60,  "unit": "mg/dL", "critical_high": None, "critical_low": 30},
        "LDL Cholesterol":                  {"min": 0,   "max": 100, "unit": "mg/dL", "critical_high": 190, "critical_low": None},
        "LDL Cholesterol, direct":          {"min": 0,   "max": 100, "unit": "mg/dL", "critical_high": 190, "critical_low": None},
        "LDL Cholesterol, direct (PHO)":    {"min": 0,   "max": 100, "unit": "mg/dL", "critical_high": 190, "critical_low": None},
        "LDL":                              {"min": 0,   "max": 100, "unit": "mg/dL", "critical_high": 190, "critical_low": None},

        # ── Liver ────────────────────────────────────────────
        "ALT":                              {"min": 7,   "max": 56,  "unit": "U/L",   "critical_high": 200, "critical_low": None},
        "ALT (SGPT)":                       {"min": 7,   "max": 56,  "unit": "U/L",   "critical_high": 200, "critical_low": None},
        "AST":                              {"min": 10,  "max": 40,  "unit": "U/L",   "critical_high": 200, "critical_low": None},
        "AST (SGOT)":                       {"min": 10,  "max": 40,  "unit": "U/L",   "critical_high": 200, "critical_low": None},
        "Albumin":                          {"min": 3.5, "max": 5.0, "unit": "g/dL",  "critical_high": None, "critical_low": 2.0},
        "Albumin (PHO)":                    {"min": 3.5, "max": 5.0, "unit": "g/dL",  "critical_high": None, "critical_low": 2.0},
        "Total Protein":                    {"min": 6.4, "max": 8.3, "unit": "g/dL",  "critical_high": None, "critical_low": 4.0},
        "Total Protein (PHO)":              {"min": 6.4, "max": 8.3, "unit": "g/dL",  "critical_high": None, "critical_low": 4.0},
        "Bilirubin":                        {"min": 0.1, "max": 1.2, "unit": "mg/dL", "critical_high": 15,  "critical_low": None},

        # ── Kidney ───────────────────────────────────────────
        "Creatinine":                       {"min": 0.5, "max": 1.2, "unit": "mg/dL", "critical_high": 5.0, "critical_low": None},
        "Creatinine (PHO)":                 {"min": 0.4, "max": 0.9, "unit": "mg/dL", "critical_high": 5.0, "critical_low": None},
        "Urea Nitrogen":                    {"min": 6,   "max": 20,  "unit": "mg/dL", "critical_high": 100, "critical_low": None},
        "Urea Nitrogen (PHO)":              {"min": 6,   "max": 20,  "unit": "mg/dL", "critical_high": 100, "critical_low": None},
        "BUN":                              {"min": 6,   "max": 20,  "unit": "mg/dL", "critical_high": 100, "critical_low": None},

        # ── Blood / CBC ──────────────────────────────────────
        "Hemoglobin":                       {"min": 12.0,"max": 17.5,"unit": "g/dL",  "critical_high": 20,  "critical_low": 7},
        "Hb A1c":                           {"min": 4.0, "max": 5.6, "unit": "%",     "critical_high": 9.0, "critical_low": None},
        "Hb A1c (TURB)":                    {"min": 2.9, "max": 4.2, "unit": "%",     "critical_high": 9.0, "critical_low": None},
        "WBC":                              {"min": 4.5, "max": 11.0,"unit": "K/uL",  "critical_high": 30,  "critical_low": 2},
        "Platelets":                        {"min": 150, "max": 400, "unit": "K/uL",  "critical_high": 1000,"critical_low": 50},
        "RBC":                              {"min": 4.2, "max": 5.9, "unit": "M/uL",  "critical_high": None,"critical_low": None},

        # ── Thyroid ──────────────────────────────────────────
        "TSH":                              {"min": 0.4, "max": 4.0, "unit": "mIU/L", "critical_high": 10,  "critical_low": 0.1},
        "T3":                               {"min": 80,  "max": 200, "unit": "ng/dL", "critical_high": None,"critical_low": None},
        "T4":                               {"min": 5.0, "max": 12.0,"unit": "ug/dL", "critical_high": None,"critical_low": None},

        # ── Vitamins / Minerals ──────────────────────────────
        "Vitamin D":                        {"min": 30,  "max": 100, "unit": "ng/mL", "critical_high": None,"critical_low": 10},
        "Vitamin B12":                      {"min": 200, "max": 900, "unit": "pg/mL", "critical_high": None,"critical_low": 100},
        "Iron":                             {"min": 60,  "max": 170, "unit": "ug/dL", "critical_high": None,"critical_low": 30},
        "Ferritin":                         {"min": 12,  "max": 300, "unit": "ng/mL", "critical_high": None,"critical_low": 5},
        "Calcium":                          {"min": 8.5, "max": 10.5,"unit": "mg/dL", "critical_high": 13,  "critical_low": 6.5},
        "Sodium":                           {"min": 136, "max": 145, "unit": "mEq/L", "critical_high": 160, "critical_low": 120},
        "Potassium":                        {"min": 3.5, "max": 5.0, "unit": "mEq/L", "critical_high": 6.5, "critical_low": 2.5},
    }

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Strip lab suffixes like (PHO), (TURB), (HEXOKINASE) etc.
        and lowercase for fuzzy matching.
        e.g. "Glucose fasting (PHO)" → "glucose fasting"
             "Hb A1c (TURB)"         → "hb a1c"
        """
        return re.sub(r'\s*\(.*?\)', '', name).strip().lower()

    def compute_risk_vector(self, results: list) -> list:
        """
        Convert a lab panel into an 8-dim normalized vector for kNN.
        Uses fuzzy keyword matching so "(PHO)" suffixes don't break lookups.
        """
        # Build normalized lookup: stripped_name → value
        lookup = {}
        for r in results:
            name = r.get("test_name", "")
            val  = r.get("value")
            if name and val is not None:
                try:
                    lookup[self._normalize_name(name)] = float(val)
                except (TypeError, ValueError):
                    pass

        vector = []
        for canonical, keywords, lo, hi in self.RISK_VECTOR_FIELDS:
            val = None

            # Try each keyword against normalized names
            for kw in keywords:
                kw_lower = kw.lower()
                # Exact match first
                if kw_lower in lookup:
                    val = lookup[kw_lower]
                    break
                # Partial match — keyword appears in stored name
                matched = next(
                    (v for k, v in lookup.items() if kw_lower in k),
                    None
                )
                if matched is not None:
                    val = matched
                    break

            if val is None:
                # Biomarker not in this panel — use midpoint (neutral)
                val = (lo + hi) / 2

            normalized = (val - lo) / (hi - lo)
            vector.append(round(min(1.0, max(0.0, normalized)), 4))

        return vector

    def compute_risk_score(self, results: list) -> tuple[float, str]:
        """
        Compute a 0→100 composite risk score from a panel's results.
        Uses fuzzy name matching for RISK_WEIGHTS and REFERENCE_RANGES.
        """
        score = 0.0

        for r in results:
            name     = r.get("test_name", "")
            value    = r.get("value")
            severity = r.get("severity", "normal")

            if value is None:
                continue

            norm_name = self._normalize_name(name)

            # Find weight — try exact then fuzzy
            weight = self.RISK_WEIGHTS.get(name)
            if weight is None:
                weight = next(
                    (w for k, w in self.RISK_WEIGHTS.items()
                     if k.lower() in norm_name or norm_name in k.lower()),
                    3  # default weight for unknown tests
                )

            # Find reference range — try exact then fuzzy
            ref = self.REFERENCE_RANGES.get(name)
            if ref is None:
                ref = next(
                    (v for k, v in self.REFERENCE_RANGES.items()
                     if self._normalize_name(k) == norm_name),
                    None
                )

            if not ref:
                if severity == "critical":
                    score += weight * 2
                elif severity == "abnormal":
                    score += weight
                continue

            lo  = ref["min"]
            hi  = ref["max"]
            mid = (lo + hi) / 2
            rng = (hi - lo) / 2 or 1

            deviation = abs(float(value) - mid) / rng

            if severity == "critical":
                score += weight * deviation * 2.5
            elif severity == "abnormal":
                score += weight * deviation * 1.2

        score = min(100.0, round(score, 1))

        if score >= 70:
            level = "CRITICAL"
        elif score >= 40:
            level = "HIGH"
        elif score >= 15:
            level = "MODERATE"
        else:
            level = "LOW"

        return score, level


settings = Settings()