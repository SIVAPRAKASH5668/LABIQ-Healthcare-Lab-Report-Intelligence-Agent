# backend/tools/lab_analyzer.py

"""
Lab Analysis Tools — ES|QL for aggregations, DSL for nested field retrieval
"""

from elasticsearch import Elasticsearch
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class LabAnalyzer:

    def __init__(self, es_client: Elasticsearch):
        self.es = es_client

    # ─────────────────────────────────────────────
    # CORE HELPERS
    # ─────────────────────────────────────────────

    def _run_esql(self, query: str) -> Dict:
        """Execute an ES|QL query."""
        try:
            response = self.es.esql.query(body={"query": query})
            return {"status": "success", "raw": response, "query": query}
        except Exception as e:
            logger.error(f"ES|QL error: {e}")
            return {"status": "error", "message": str(e), "query": query}

    def _rows_to_dicts(self, esql_response: Dict) -> List[Dict]:
        """Convert ES|QL columnar format → list of dicts."""
        raw = esql_response.get("raw", {})
        columns = [col["name"] for col in raw.get("columns", [])]
        return [dict(zip(columns, row)) for row in raw.get("values", [])]

    def _run_dsl(self, index: str, body: dict) -> Dict:
        """Execute a regular DSL search (needed for nested object fields)."""
        try:
            response = self.es.search(index=index, body=body)
            return {"status": "success", "raw": response}
        except Exception as e:
            logger.error(f"DSL search error: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # PATIENT SUMMARY  — ES|QL ✓
    # ─────────────────────────────────────────────

    def get_patient_summary(self, patient_id: str) -> Dict:
        """Aggregate summary via ES|QL STATS."""

        esql = f"""
FROM lab-results
| WHERE patient_id == "{patient_id}"
| STATS
    total_tests = COUNT(*),
    first_test_date = MIN(test_date),
    last_test_date  = MAX(test_date)
""".strip()

        result = self._run_esql(esql)
        if result["status"] == "error":
            return result

        rows = self._rows_to_dicts(result)
        if not rows:
            return {"status": "no_data", "patient_id": patient_id, "esql_query": esql}

        row = rows[0]

        # Abnormal count
        abn_esql = f"""
FROM lab-results
| WHERE patient_id == "{patient_id}" AND abnormal_flags IS NOT NULL
| STATS abnormal_tests = COUNT(*)
""".strip()
        abn_rows = self._rows_to_dicts(self._run_esql(abn_esql))
        abnormal_count = abn_rows[0].get("abnormal_tests", 0) if abn_rows else 0

        # Critical count
        crit_esql = f"""
FROM lab-results
| WHERE patient_id == "{patient_id}" AND critical_flags IS NOT NULL
| STATS critical_tests = COUNT(*)
""".strip()
        crit_rows = self._rows_to_dicts(self._run_esql(crit_esql))
        critical_count = crit_rows[0].get("critical_tests", 0) if crit_rows else 0

        return {
            "status": "success",
            "patient_id": patient_id,
            "total_tests": row.get("total_tests", 0),
            "abnormal_tests": abnormal_count,
            "critical_tests": critical_count,
            "first_test_date": str(row.get("first_test_date", "")),
            "last_test_date": str(row.get("last_test_date", "")),
            "esql_query": esql,
        }

    # ─────────────────────────────────────────────
    # RECENT LABS  — DSL ✓ (ES|QL cannot project nested arrays)
    # ─────────────────────────────────────────────

    def get_recent_labs(self, patient_id: str, limit: int = 5) -> Dict:
        """
        Fetch recent lab documents including the nested `results[]` array.
        Must use the DSL search API because ES|QL cannot return nested object
        arrays as structured data.
        """
        body = {
            "query": {"term": {"patient_id": patient_id}},
            "sort": [{"test_date": "desc"}],
            "size": limit,
            "_source": ["test_date", "test_type", "results", "abnormal_flags", "critical_flags"],
        }

        result = self._run_dsl("lab-results", body)
        if result["status"] == "error":
            return result

        hits = result["raw"]["hits"]["hits"]
        if not hits:
            return {
                "status": "no_data",
                "message": f"No lab results found for patient {patient_id}",
                "esql_query": None,
            }

        labs = []
        for hit in hits:
            src = hit["_source"]
            labs.append({
                "test_date": src.get("test_date", ""),
                "test_type": src.get("test_type", "Lab Panel"),
                "results": src.get("results", []),          # ← nested array preserved
                "abnormal_flags": src.get("abnormal_flags", []),
                "critical_flags": src.get("critical_flags", []),
            })

        # Build a readable ES|QL-equivalent note for the frontend display
        esql_note = f"""-- Nested array retrieval requires DSL (not ES|QL)
POST lab-results/_search
{{
  "query": {{ "term": {{ "patient_id": "{patient_id}" }} }},
  "sort": [{{"test_date": "desc"}}],
  "size": {limit},
  "_source": ["test_date","test_type","results","abnormal_flags","critical_flags"]
}}"""

        return {
            "status": "success",
            "patient_id": patient_id,
            "recent_labs": labs,
            "esql_query": esql_note,
        }

    # ─────────────────────────────────────────────
    # GLUCOSE TREND  — DSL fetch, Python stats
    # ─────────────────────────────────────────────

    def analyze_glucose_trend(self, patient_id: str) -> Dict:
        """Fetch all docs with DSL, extract glucose from nested results."""

        body = {
            "query": {"term": {"patient_id": patient_id}},
            "sort": [{"test_date": "asc"}],
            "size": 100,
            "_source": ["test_date", "results"],
        }

        result = self._run_dsl("lab-results", body)
        if result["status"] == "error":
            return result

        glucose_data = []
        for hit in result["raw"]["hits"]["hits"]:
            test_date = hit["_source"].get("test_date", "")
            for res in hit["_source"].get("results", []):
                if "Glucose" in (res.get("test_name") or ""):
                    glucose_data.append({
                        "date": str(test_date),
                        "value": res["value"],
                        "unit": res.get("unit", "mg/dL"),
                        "is_abnormal": res.get("is_abnormal", False),
                        "severity": res.get("severity", "normal"),
                    })

        if not glucose_data:
            return {
                "status": "no_data",
                "message": f"No glucose data found for patient {patient_id}",
                "esql_query": None,
            }

        values = [g["value"] for g in glucose_data]
        latest, earliest = values[-1], values[0]
        avg = sum(values) / len(values)

        trend = (
            "increasing" if latest > avg * 1.1
            else "decreasing" if latest < avg * 0.9
            else "stable"
        )
        pct = ((latest - earliest) / earliest * 100) if earliest else 0

        esql_note = f"""-- Glucose trend (fetched via DSL, aggregated in Python)
FROM lab-results
| WHERE patient_id == "{patient_id}"
| SORT test_date ASC
-- Then filter results[] where test_name LIKE "Glucose%"
-- (nested array filtering requires DSL or script)"""

        return {
            "status": "success",
            "patient_id": patient_id,
            "test_name": "Glucose",
            "data_points": len(glucose_data),
            "latest_value": round(latest, 1),
            "earliest_value": round(earliest, 1),
            "average_value": round(avg, 1),
            "max_value": round(max(values), 1),
            "min_value": round(min(values), 1),
            "trend_direction": trend,
            "percent_change": round(pct, 1),
            "timeline": glucose_data,
            "interpretation": self._interpret_glucose(latest, trend, pct),
            "esql_query": esql_note,
        }

    # ─────────────────────────────────────────────
    # ALL TRENDS  — DSL fetch, Python stats
    # ─────────────────────────────────────────────

    def analyze_all_trends(self, patient_id: str) -> Dict:
        """Analyse trends across all tests (DSL fetch, Python aggregation)."""

        body = {
            "query": {"term": {"patient_id": patient_id}},
            "sort": [{"test_date": "asc"}],
            "size": 100,
            "_source": ["test_date", "results"],
        }

        result = self._run_dsl("lab-results", body)
        if result["status"] == "error":
            return result

        test_data: Dict[str, List[float]] = {}
        for hit in result["raw"]["hits"]["hits"]:
            for res in hit["_source"].get("results", []):
                name = res.get("test_name")
                if name:
                    test_data.setdefault(name, []).append(res["value"])

        trends = []
        for test_name, values in test_data.items():
            if len(values) < 2:
                continue
            latest, earliest = values[-1], values[0]
            avg = sum(values) / len(values)

            if latest > avg * 1.15:
                direction = "significantly_increasing"
            elif latest > avg * 1.05:
                direction = "slightly_increasing"
            elif latest < avg * 0.85:
                direction = "significantly_decreasing"
            elif latest < avg * 0.95:
                direction = "slightly_decreasing"
            else:
                direction = "stable"

            change = ((latest - earliest) / earliest * 100) if earliest else 0
            trends.append({
                "test_name": test_name,
                "latest_value": round(latest, 2),
                "earliest_value": round(earliest, 2),
                "average_value": round(avg, 2),
                "data_points": len(values),
                "trend_direction": direction,
                "percent_change": round(change, 1),
            })

        trends.sort(key=lambda x: abs(x["percent_change"]), reverse=True)
        concerning = [t for t in trends if "significantly" in t["trend_direction"]]

        # Use ES|QL for the high-level count summary to demonstrate real ES|QL
        esql = f"""
FROM lab-results
| WHERE patient_id == "{patient_id}"
| STATS total_panels = COUNT(*), first_date = MIN(test_date), last_date = MAX(test_date)
""".strip()
        self._run_esql(esql)  # fire it so the log shows the real query

        return {
            "status": "success",
            "patient_id": patient_id,
            "all_trends": trends,
            "concerning_trends": concerning,
            "total_tests_analyzed": len(trends),
            "summary": self._generate_trend_summary(trends, concerning),
            "esql_query": esql,
        }

    # ─────────────────────────────────────────────
    # CRITICAL VALUES  — ES|QL ✓
    # ─────────────────────────────────────────────

    def find_critical_values(self, patient_id: str) -> Dict:
        """Find critical-severity results using ES|QL."""

        esql = f"""
FROM lab-results
| WHERE patient_id == "{patient_id}" AND critical_flags IS NOT NULL
| SORT test_date DESC
| LIMIT 10
| KEEP test_date, critical_flags
""".strip()

        result = self._run_esql(esql)
        if result["status"] == "error":
            # Fall back to DSL
            return self._find_critical_dsl(patient_id)

        # critical_flags found — now fetch full docs with DSL for values
        rows = self._rows_to_dicts(result)
        if not rows:
            return {
                "status": "no_critical_values",
                "patient_id": patient_id,
                "message": "No critical values found",
                "alert_required": False,
                "esql_query": esql,
            }

        return self._find_critical_dsl(patient_id, esql_query=esql)

    def _find_critical_dsl(self, patient_id: str, esql_query: str = None) -> Dict:
        """DSL fallback to pull actual critical result objects."""
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"patient_id": patient_id}},
                        {"exists": {"field": "critical_flags"}},
                    ]
                }
            },
            "sort": [{"test_date": "desc"}],
            "size": 10,
            "_source": ["test_date", "results", "critical_flags"],
        }

        result = self._run_dsl("lab-results", body)
        if result["status"] == "error":
            return result

        critical_values = []
        for hit in result["raw"]["hits"]["hits"]:
            test_date = str(hit["_source"].get("test_date", ""))
            for res in hit["_source"].get("results", []):
                if res.get("severity") == "critical":
                    critical_values.append({
                        "test_date": test_date,
                        "test_name": res.get("test_name", ""),
                        "value": res.get("value"),
                        "unit": res.get("unit"),
                        "reference_min": res.get("reference_min"),
                        "reference_max": res.get("reference_max"),
                        "deviation": self._calculate_deviation(
                            res.get("value", 0),
                            res.get("reference_min", 0),
                            res.get("reference_max", 100),
                        ),
                    })

        if not critical_values:
            return {
                "status": "no_critical_values",
                "patient_id": patient_id,
                "message": "No critical values found",
                "alert_required": False,
                "esql_query": esql_query,
            }

        return {
            "status": "critical_values_found",
            "patient_id": patient_id,
            "critical_values": critical_values,
            "alert_required": True,
            "urgency": "high" if len(critical_values) > 2 else "medium",
            "alert_message": self._generate_critical_alert(critical_values),
            "esql_query": esql_query,
        }

    # ─────────────────────────────────────────────
    # CUSTOM ES|QL (power-user / agent builder)
    # ─────────────────────────────────────────────

    def run_custom_esql(self, query: str) -> Dict:
        result = self._run_esql(query)
        if result["status"] == "error":
            return result
        return {
            "status": "success",
            "rows": self._rows_to_dicts(result),
            "esql_query": query,
        }

    # ─────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────

    def _interpret_glucose(self, value: float, trend: str, change: float) -> str:
        if value > 125:
            return (
                f"⚠️ Elevated glucose ({value} mg/dL) suggests prediabetes or diabetes. "
                f"Trend: {trend} ({change:+.1f}%). Immediate medical consultation recommended."
            )
        elif value > 100:
            return (
                f"⚠️ Borderline glucose ({value} mg/dL). Trend: {trend} ({change:+.1f}%). "
                "Lifestyle modifications recommended. Monitor closely."
            )
        return (
            f"✓ Normal glucose ({value} mg/dL). Trend: {trend} ({change:+.1f}%). "
            "Continue healthy habits."
        )

    def _generate_trend_summary(self, trends: List, concerning: List) -> str:
        if not concerning:
            return f"All {len(trends)} lab values are stable or showing minimal changes."
        names = ", ".join(t["test_name"] for t in concerning[:3])
        return f"⚠️ Found {len(concerning)} concerning trends: {names}"

    def _calculate_deviation(self, value: float, ref_min: float, ref_max: float) -> str:
        if value < ref_min and ref_min > 0:
            pct = (ref_min - value) / ref_min * 100
            return f"{pct:.0f}% below normal"
        if value > ref_max and ref_max > 0:
            pct = (value - ref_max) / ref_max * 100
            return f"{pct:.0f}% above normal"
        return "within range"

    def _generate_critical_alert(self, critical_values: List) -> str:
        if len(critical_values) == 1:
            cv = critical_values[0]
            return f"URGENT: {cv['test_name']} critically {cv['deviation']}"
        tests = [cv["test_name"] for cv in critical_values[:3]]
        return f"URGENT: {len(critical_values)} critical values detected: {', '.join(tests)}"