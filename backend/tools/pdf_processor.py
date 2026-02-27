# backend/tools/pdf_processor.py
"""
PDF Lab Report Processor
Fixes applied:
  1. Fuzzy reference range lookup
  2. Multiline test name cleanup
  3. Flag words between value and unit
  4. One-sided reference ranges (< 150, > 50)
  5. Deviation % vs reference midpoint
  6. [NEW] Computes risk_vector + risk_score for ES kNN/scoring
"""

import pdfplumber
import re
from typing import Dict, List, Optional
from datetime import datetime
import logging
from core.config import settings

logger = logging.getLogger(__name__)


class LabReportProcessor:

    def __init__(self):
        self.reference_ranges = settings.REFERENCE_RANGES
        self.skip_keywords = [
            "Normal:", "Optimal:", "Borderline:", "Increased Risk",
            "Decreased Risk", "High Risk", "Low Risk", "Near Optimal:",
            "High:", "Low:", "Critical:", "Abnormal:", "Reference:",
            "Ref Range:", "Range:", "Men:", "Women:", "Male:", "Female:",
            "Desirable:", "Please note", "Daily internal", "External Quality",
            "Techn.", "This report", "This parameter", "This investigation",
            "Recommendations", "Note:", "Page ", "P.O. Box", "Tel:", "Fax:",
            "E-mail:", "Website:", "Insurance:", "Remarks:", "Physician:",
        ]

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def process_pdf(self, pdf_path: str, patient_id: str) -> Dict:
        logger.info(f"📄 Processing PDF: {pdf_path} for patient {patient_id}")
        try:
            text = self._extract_text(pdf_path)
            if not text or len(text) < 50:
                return {"status": "error", "message": "Could not extract text from PDF"}

            results = self._parse_test_results(text)
            if not results:
                return {"status": "error", "message": "No lab results found in PDF"}

            test_date = self._extract_date(text)
            lab_name  = self._extract_lab_name(text)

            abnormal_flags = [r["test_name"] for r in results if r["is_abnormal"]]
            critical_flags = [r["test_name"] for r in results if r["severity"] == "critical"]

            # ── NEW: compute ES scoring fields ────────────────
            risk_vector        = settings.compute_risk_vector(results)
            risk_score, level  = settings.compute_risk_score(results)

            document = {
                "patient_id":     patient_id,
                "test_date":      test_date.isoformat(),
                "test_type":      self._infer_test_type(results),
                "lab_name":       lab_name,
                "results":        results,
                "report_text":    text[:5000],
                "abnormal_flags": abnormal_flags,
                "critical_flags": critical_flags,
                "processed_at":   datetime.now().isoformat(),
                "source_file":    pdf_path.split("/")[-1],
                # ── ES scoring fields (new) ───────────────────
                "risk_vector":    risk_vector,   # 8-dim kNN vector
                "risk_score":     risk_score,    # 0-100 composite score
                "risk_level":     level,         # LOW/MODERATE/HIGH/CRITICAL
            }

            logger.info(
                f"✅ {len(results)} results | "
                f"Abnormal: {len(abnormal_flags)} | Critical: {len(critical_flags)} | "
                f"Risk: {risk_score} ({level}) | Vector: {risk_vector}"
            )
            return {"status": "success", "document": document}

        except Exception as e:
            logger.error(f"❌ Error processing PDF: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────────────────────
    # FIX 1 — Fuzzy reference-range lookup
    # ─────────────────────────────────────────────────────────────

    def _lookup_ref(self, test_name: str) -> Dict:
        if test_name in self.reference_ranges:
            return self.reference_ranges[test_name]
        stripped = re.sub(r'\s*\([A-Z]{2,6}\)\s*$', '', test_name).strip()
        if stripped in self.reference_ranges:
            return self.reference_ranges[stripped]
        name_lower = test_name.lower()
        best_key, best_len = None, 0
        for key in self.reference_ranges:
            key_lower = key.lower()
            if key_lower in name_lower and len(key_lower) > best_len:
                best_key, best_len = key, len(key_lower)
        return self.reference_ranges[best_key] if best_key else {}

    # ─────────────────────────────────────────────────────────────
    # FIX 2 — Clean multiline test names
    # ─────────────────────────────────────────────────────────────

    def _clean_test_name(self, raw: str) -> str:
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines:
            return ""
        name = lines[-1]
        for pat in [r'\(Serum\)$', r'\(EDTA\s*blood\)$', r'\(Plasma\)$',
                    r'\(Urine\)$', r'\(Whole\s*blood\)$']:
            name = re.sub(pat, '', name, flags=re.IGNORECASE).strip()
        return name.strip()

    # ─────────────────────────────────────────────────────────────
    # FIX 3 & 4 — Parse results with flag words & one-sided ranges
    # ─────────────────────────────────────────────────────────────

    def _parse_test_results(self, text: str) -> List[Dict]:
        results = []
        seen    = set()

        pat_a = re.compile(
            r'^([A-Za-z][A-Za-z0-9\s\(\),/\-\.]*?)'
            r'\s+(\d+\.?\d*)'
            r'(?:\s+(?:high|low|normal|abnormal|critical|H|L))?'
            r'\s+([a-zA-Z/%]+(?:/[a-zA-Z]+)?)'
            r'\s+(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)',
            re.IGNORECASE | re.MULTILINE,
        )
        pat_b = re.compile(
            r'^([A-Za-z][A-Za-z0-9\s\(\),/\-\.]*?)'
            r'\s+(\d+\.?\d*)'
            r'(?:\s+(?:high|low|normal|abnormal|critical|H|L))?'
            r'\s+([a-zA-Z/%]+(?:/[a-zA-Z]+)?)'
            r'\s+([<>])\s*(\d+\.?\d*)',
            re.IGNORECASE | re.MULTILINE,
        )
        pat_c = re.compile(
            r'([A-Za-z][A-Za-z0-9\s\(\),/\-\.]+):\s*(\d+\.?\d*)\s*([a-zA-Z/%]*)'
            r'\s*\(?Ref(?:erence)?:\s*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)\)?',
            re.IGNORECASE,
        )

        def _build(name_raw, value_s, unit_s, ref_min, ref_max):
            name = self._clean_test_name(name_raw)
            if not name or len(name) < 3 or len(name) > 80:
                return
            if any(kw.lower() in name.lower() for kw in self.skip_keywords):
                return
            if sum(c.isalpha() for c in name) < 3:
                return
            key = name.lower().strip()
            if key in seen:
                return
            try:
                value = float(value_s)
                unit  = unit_s.strip()
                r_min = float(ref_min)
                r_max = float(ref_max)
                if r_min >= r_max and r_max != 0:
                    return
            except (ValueError, TypeError):
                return

            if unit.lower() in {"high", "low", "normal", "abnormal", "-", ""}:
                ref_data = self._lookup_ref(name)
                unit = ref_data.get("unit", "")
                if not unit:
                    for kw, u in [
                        ("glucose","mg/dL"),("cholesterol","mg/dL"),
                        ("triglyceride","mg/dL"),("hdl","mg/dL"),
                        ("ldl","mg/dL"),("hemoglobin","g/dL"),
                        ("albumin","g/dL"),("creatinine","mg/dL"),
                        ("protein","g/dL"),("urea","mg/dL"),
                        ("bilirubin","mg/dL"),("calcium","mg/dL"),
                    ]:
                        if kw in name.lower():
                            unit = u
                            break

            is_abnormal = value < r_min or value > r_max

            ref_data = self._lookup_ref(name)
            severity = "normal"
            if ref_data.get("critical_high") and value > ref_data["critical_high"]:
                severity = "critical"
            elif ref_data.get("critical_low") and value < ref_data["critical_low"]:
                severity = "critical"
            elif is_abnormal:
                severity = "abnormal"

            ref_mid   = (r_min + r_max) / 2 if r_max else None
            deviation = round((value - ref_mid) / ref_mid * 100, 1) if ref_mid else None

            seen.add(key)
            results.append({
                "test_name":     name,
                "value":         value,
                "unit":          unit,
                "reference_min": r_min,
                "reference_max": r_max,
                "is_abnormal":   is_abnormal,
                "severity":      severity,
                "deviation_pct": deviation,
            })

        for m in pat_a.finditer(text):
            _build(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))

        for m in pat_b.finditer(text):
            op, bound = m.group(4), float(m.group(5))
            r_min = "0" if op == "<" else str(bound)
            r_max = str(bound) if op == "<" else str(bound * 2)
            _build(m.group(1), m.group(2), m.group(3), r_min, r_max)

        for m in pat_c.finditer(text):
            _build(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))

        return results

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _extract_text(self, pdf_path: str) -> str:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text

    def _extract_date(self, text: str) -> datetime:
        patterns = [
            r'\d{2}\.\d{2}\.\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    from dateutil import parser as dp
                    return dp.parse(m.group(0), dayfirst=True)
                except Exception:
                    pass
        return datetime.now()

    def _extract_lab_name(self, text: str) -> str:
        for line in text[:500].split("\n")[:8]:
            line = line.strip()
            if any(kw in line for kw in ["Lab", "Laboratory", "Medical", "Hospital", "Diagnostic"]):
                if 10 < len(line) < 80:
                    return line
        return "Medical Laboratory"

    def _infer_test_type(self, results: List[Dict]) -> str:
        names = [r["test_name"].lower() for r in results]
        if any("glucose" in n for n in names) and any("cholesterol" in n for n in names):
            return "Comprehensive Metabolic Panel"
        if any("glucose" in n for n in names):
            return "Glucose Panel"
        if any(k in n for n in names for k in ("cholesterol","hdl","ldl","triglyceride")):
            return "Lipid Panel"
        if any("hemoglobin" in n for n in names):
            return "Complete Blood Count"
        return "Lab Panel"


    # ─────────────────────────────────────────────────────────────
    # Batch re-indexing helper
    # Call this once to backfill risk_vector/risk_score on existing docs
    # ─────────────────────────────────────────────────────────────

    def backfill_risk_fields(self, es_client) -> int:
        """
        Scan all existing lab-results documents that lack risk_vector
        and update them in-place. Run once after deploying this version.

        Usage:
            from tools.pdf_processor import LabReportProcessor
            from core.elasticsearch_client import get_es_client
            proc = LabReportProcessor()
            updated = proc.backfill_risk_fields(get_es_client())
            print(f"Updated {updated} documents")
        """
        updated = 0
        page_size = 100

        resp = es_client.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "query": {"bool": {"must_not": {"exists": {"field": "risk_vector"}}}},
                "size":  page_size,
                "_source": ["results"],
                "sort":  ["_doc"],
            },
            scroll="2m",
        )

        scroll_id = resp["_scroll_id"]
        hits      = resp["hits"]["hits"]

        while hits:
            for hit in hits:
                doc_id  = hit["_id"]
                results = hit["_source"].get("results", [])

                risk_vector       = settings.compute_risk_vector(results)
                risk_score, level = settings.compute_risk_score(results)

                es_client.client.update(
                    index=settings.LAB_RESULTS_INDEX,
                    id=doc_id,
                    body={"doc": {
                        "risk_vector": risk_vector,
                        "risk_score":  risk_score,
                        "risk_level":  level,
                    }},
                )
                updated += 1

            resp     = es_client.client.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp["_scroll_id"]
            hits      = resp["hits"]["hits"]

        es_client.client.clear_scroll(scroll_id=scroll_id)
        logger.info(f"✅ Backfilled {updated} documents with risk_vector/risk_score")
        return updated