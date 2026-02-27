# backend/api/patients.py
from fastapi import APIRouter, HTTPException
import time
from core.elasticsearch_client import get_es_client
from tools.lab_analyzer import LabAnalyzer

router    = APIRouter()
es_client = get_es_client()
analyzer  = LabAnalyzer(es_client.client)

INDEX = "lab-results"


def _run_esql(query: str) -> dict:
    from api.esql import run_esql_query
    return run_esql_query(query)


def _flatten(v) -> str:
    """ES text fields can return as list ['CRITICAL'] or string — normalize both."""
    if v is None:
        return ""
    if isinstance(v, list):
        return str(v[0]).strip() if v else ""
    return str(v).strip()


def _safe_float(v, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _date_str(v) -> str:
    if not v:
        return ""
    return str(v)[:10]


# ── GET /api/patients ─────────────────────────────────────────
@router.get("/api/patients")
async def list_patients():
    """
    List all patients with panel counts and latest test date.
    Uses DSL aggs instead of ES|QL to avoid COUNT(*) WHERE limitation.
    """
    try:
        resp = es_client.client.search(index=INDEX, body={
            "size": 0,
            "aggs": {
                "by_patient": {
                    "terms": {"field": "patient_id", "size": 200},
                    "aggs": {
                        "last_test":    {"max":    {"field": "test_date"}},
                        "first_test":   {"min":    {"field": "test_date"}},
                        "avg_risk":     {"avg":    {"field": "risk_score"}},
                        "max_risk":     {"max":    {"field": "risk_score"}},
                        "has_critical": {"filter": {"exists": {"field": "critical_flags"}}},
                        "has_abnormal": {"filter": {"exists": {"field": "abnormal_flags"}}},
                    }
                }
            }
        })
        buckets = resp.get("aggregations", {}).get("by_patient", {}).get("buckets", [])
        patients = []
        for b in sorted(buckets, key=lambda x: x["key"]):
            patients.append({
                "patient_id":   b["key"],
                "total_tests":  _safe_int(b.get("doc_count"), 0),
                "critical":     _safe_int(b.get("has_critical", {}).get("doc_count"), 0),
                "abnormal":     _safe_int(b.get("has_abnormal", {}).get("doc_count"), 0),
                "last_test":    _date_str(
                    b.get("last_test", {}).get("value_as_string") or
                    b.get("last_test", {}).get("value")
                ),
                "first_test":   _date_str(
                    b.get("first_test", {}).get("value_as_string") or
                    b.get("first_test", {}).get("value")
                ),
                "avg_risk":     round(_safe_float(b.get("avg_risk",  {}).get("value")), 1),
                "max_risk":     round(_safe_float(b.get("max_risk",  {}).get("value")), 1),
            })
        return {"patients": patients, "total": len(patients)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── GET /api/patients/{id}/summary ───────────────────────────
@router.get("/api/patients/{patient_id}/summary")
async def get_patient_summary(patient_id: str):
    result = analyzer.get_patient_summary(patient_id)
    if result["status"] == "error":
        raise HTTPException(500, result["message"])
    return result


# ── GET /api/patients/{id}/biomarkers ────────────────────────
@router.get("/api/patients/{patient_id}/biomarkers")
async def get_biomarkers(patient_id: str):
    try:
        resp = es_client.client.search(index=INDEX, body={
            "query": {"term": {"patient_id": patient_id}},
            "sort":  [{"test_date": "asc"}],
            "size":  200,
            "_source": True,
        })
        hits = resp["hits"]["hits"]
    except Exception as e:
        raise HTTPException(500, str(e))

    series: dict = {}
    for hit in hits:
        src  = hit["_source"]
        date = _date_str(src.get("test_date", ""))
        for r in src.get("results", []):
            name = (r.get("test_name") or "").strip()
            val  = r.get("value")
            if not name or val is None:
                continue
            if any(name.startswith(p) for p in (
                "Normal", "Optimal", "Increased", "Decreased",
                "High", "Low", "Borderline", "Please", "Note"
            )):
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if name not in series:
                series[name] = {
                    "dates": [], "values": [],
                    "unit":        r.get("unit", ""),
                    "ref_min":     r.get("reference_min"),
                    "ref_max":     r.get("reference_max"),
                    "is_abnormal": bool(r.get("is_abnormal", False)),
                    "severity":    r.get("severity", "normal"),
                }
            series[name]["dates"].append(date)
            series[name]["values"].append(val)
            if r.get("severity") in ("critical", "abnormal"):
                series[name]["is_abnormal"] = True
                series[name]["severity"]    = r.get("severity")

    biomarkers = []
    for name, s in series.items():
        vals = s["values"]
        if not vals:
            continue
        latest = vals[-1]
        avg    = sum(vals) / len(vals)
        r_min  = s["ref_min"] or 0
        r_max  = s["ref_max"] or 0
        if r_max > 0:
            ref_mid   = (r_min + r_max) / 2
            deviation = round((latest - ref_mid) / ref_mid * 100, 1)
        else:
            deviation = round((latest - avg) / avg * 100, 1) if avg else 0
        trend  = "up" if latest > avg * 1.05 else "down" if latest < avg * 0.95 else "stable"
        is_abn = s["is_abnormal"] or (r_max and latest > r_max) or (r_min and latest < r_min)
        biomarkers.append({
            "name": name, "unit": s["unit"],
            "ref_min": r_min or None, "ref_max": r_max or None,
            "latest": round(latest, 2), "average": round(avg, 2),
            "deviation_pct": deviation, "trend": trend,
            "is_abnormal": bool(is_abn), "severity": s["severity"],
            "dates": s["dates"], "values": [round(v, 2) for v in vals],
            "data_points": len(vals),
        })

    biomarkers.sort(key=lambda x: (
        x["severity"] != "critical",
        x["severity"] != "abnormal",
        -abs(x["deviation_pct"] or 0)
    ))
    return {
        "status": "success",
        "patient_id": patient_id,
        "biomarkers": biomarkers,
        # Also expose as flat "results" so llmchat context builder finds it
        "results": [
            {
                "test_name":     b["name"],
                "value":         b["latest"],
                "unit":          b["unit"],
                "reference_min": b["ref_min"],
                "reference_max": b["ref_max"],
                "is_abnormal":   b["is_abnormal"],
                "severity":      b["severity"],
                "deviation_pct": b["deviation_pct"],
            }
            for b in biomarkers
        ],
        "total": len(biomarkers),
    }


# ── GET /api/patients/{id}/risk-trend ────────────────────────
@router.get("/api/patients/{patient_id}/risk-trend")
async def get_risk_trend(patient_id: str):
    """
    Per-visit risk scores and flag counts.
    This is the endpoint llmchat.py calls for trend/history questions.
    Returns shape with "trend" key containing the visits array.
    """
    try:
        resp = es_client.client.search(index=INDEX, body={
            "query": {"term": {"patient_id": patient_id}},
            "sort":  [{"test_date": "asc"}],
            "size":  50,
            "_source": [
                "test_date", "test_type", "risk_score", "risk_level",
                "critical_flags", "abnormal_flags",
            ],
        })
        hits = resp["hits"]["hits"]
    except Exception as e:
        raise HTTPException(500, str(e))

    if not hits:
        return {
            "patient_id":  patient_id,
            "visits":      0,
            "trend":       [],
            "direction":   "unknown",
            "pct_change":  0.0,
            "first_score": 0,
            "last_score":  0,
        }

    trend_rows = []
    for hit in hits:
        src = hit["_source"]
        rs  = _safe_float(src.get("risk_score"), 0.0)
        cf  = src.get("critical_flags") or []
        af  = src.get("abnormal_flags") or []

        # critical_flags / abnormal_flags may be a string or list
        if isinstance(cf, str):
            cf = [cf] if cf else []
        if isinstance(af, str):
            af = [af] if af else []

        trend_rows.append({
            "date":           _date_str(src.get("test_date")),
            "test_type":      _flatten(src.get("test_type")) or "Lab Panel",
            "risk_score":     round(rs, 1),
            "risk_level":     _flatten(src.get("risk_level")) or _risk_label(rs),
            "critical":       len(cf),
            "critical_flags": cf,
            "abnormal":       len(af),
            "abnormal_flags": af,
        })

    first_score = trend_rows[0]["risk_score"]  if trend_rows else 0.0
    last_score  = trend_rows[-1]["risk_score"] if trend_rows else 0.0

    pct_change = 0.0
    if first_score and first_score != 0:
        pct_change = round(((last_score - first_score) / first_score) * 100, 1)

    if pct_change <= -10:
        direction = "improving ↓"
    elif pct_change >= 10:
        direction = "worsening ↑"
    else:
        direction = "stable →"

    return {
        "patient_id":  patient_id,
        "visits":      len(trend_rows),
        "trend":       trend_rows,       # ← key used by llmchat._extract_visits()
        "direction":   direction,
        "pct_change":  pct_change,
        "first_score": first_score,
        "last_score":  last_score,
    }


# ── GET /api/patients/{id}/risk-score ────────────────────────
@router.get("/api/patients/{patient_id}/risk-score")
async def get_risk_score(patient_id: str):
    from api.esql import run_esql_query
    ab_r  = run_esql_query(
        f'FROM lab-results | WHERE patient_id == "{patient_id}" '
        f'AND abnormal_flags IS NOT NULL | STATS abnormal_panels = COUNT(*)'
    )
    tot_r = run_esql_query(
        f'FROM lab-results | WHERE patient_id == "{patient_id}" '
        f'| STATS total_panels = COUNT(*)'
    )
    abnormal = (ab_r["rows"][0].get("abnormal_panels") or 0) if ab_r["rows"] else 0
    total    = (tot_r["rows"][0].get("total_panels") or 1)   if tot_r["rows"] else 1

    try:
        resp    = es_client.client.search(index=INDEX, body={
            "query": {"term": {"patient_id": patient_id}},
            "sort":  [{"test_date": "desc"}],
            "size":  1,
            "_source": True,
        })
        results = (
            resp["hits"]["hits"][0]["_source"].get("results", [])
            if resp["hits"]["hits"] else []
        )
    except Exception:
        results = []

    lookup = {r.get("test_name", ""): r for r in results}

    def _val(*fragments):
        for k, v in lookup.items():
            if any(f.lower() in k.lower() for f in fragments):
                try:
                    return float(v.get("value"))
                except (TypeError, ValueError):
                    pass
        return None

    chol = _val("cholesterol, total", "total cholesterol")
    trig = _val("triglycerides")
    hdl  = _val("hdl cholesterol", "hdl")
    gluc = _val("glucose fasting", "glucose")

    risk_factors, score = [], 0
    if chol and chol > 200:
        pts = min(25, int((chol - 200) / 4))
        score += pts
        risk_factors.append({
            "factor": "High Cholesterol", "value": f"{chol} mg/dL",
            "points": pts, "severity": "high" if chol > 240 else "medium",
        })
    if trig and trig > 150:
        pts = min(35, int((trig - 150) / 15))
        score += pts
        risk_factors.append({
            "factor": "High Triglycerides", "value": f"{trig} mg/dL",
            "points": pts, "severity": "critical" if trig > 500 else "high",
        })
    if hdl and hdl < 50:
        pts = min(20, int((50 - hdl) / 2))
        score += pts
        risk_factors.append({
            "factor": "Low HDL", "value": f"{hdl} mg/dL",
            "points": pts, "severity": "high" if hdl < 30 else "medium",
        })
    if gluc and gluc > 100:
        pts = min(15, int((gluc - 100) / 5))
        score += pts
        risk_factors.append({
            "factor": "Elevated Glucose", "value": f"{gluc} mg/dL",
            "points": pts, "severity": "high" if gluc > 126 else "medium",
        })

    score = min(100, score)
    level = "CRITICAL" if score >= 70 else "HIGH" if score >= 40 else "MODERATE" if score >= 20 else "LOW"
    color = "red" if score >= 70 else "orange" if score >= 40 else "yellow" if score >= 20 else "green"
    return {
        "patient_id": patient_id, "score": score, "level": level, "color": color,
        "risk_factors": risk_factors, "abnormal_panels": abnormal, "total_panels": total,
    }


# ── GET /api/patients/{id}/scoring-summary ───────────────────
@router.get("/api/patients/{patient_id}/scoring-summary")
async def get_scoring_summary(patient_id: str):
    """Risk percentile + kNN similar patients via dense_vector cosine."""
    try:
        own_resp = es_client.client.search(index=INDEX, body={
            "query": {"term": {"patient_id": patient_id}},
            "sort":  [{"test_date": "desc"}],
            "size":  1,
            "_source": ["risk_score", "risk_level", "risk_vector"],
        })
        own_hits = own_resp["hits"]["hits"]
        if not own_hits:
            return {"patient_id": patient_id, "risk_score": 0,
                    "percentile": 0, "similar_patients": []}

        own_src    = own_hits[0]["_source"]
        own_score  = _safe_float(own_src.get("risk_score"), 0.0)
        own_level  = _flatten(own_src.get("risk_level")) or _risk_label(own_score)
        own_vector = own_src.get("risk_vector")

        # Percentile
        total = es_client.client.count(index=INDEX).get("count", 1)
        lower = es_client.client.count(index=INDEX, body={
            "query": {"range": {"risk_score": {"lt": own_score}}}
        }).get("count", 0)
        percentile = round((lower / max(total, 1)) * 100)

        # kNN similar patients
        similar = []
        if own_vector and isinstance(own_vector, list):
            try:
                knn_resp = es_client.client.search(index=INDEX, body={
                    "knn": {
                        "field":          "risk_vector",
                        "query_vector":   own_vector,
                        "k":              6,
                        "num_candidates": 30,
                    },
                    "_source": ["patient_id", "risk_score", "risk_level"],
                    "size": 6,
                })
                seen = set()
                for hit in knn_resp["hits"]["hits"]:
                    src = hit["_source"]
                    pid = src.get("patient_id", "")
                    if pid == patient_id or pid in seen:
                        continue
                    seen.add(pid)
                    similar.append({
                        "patient_id":  pid,
                        "similarity":  round(_safe_float(hit.get("_score")), 3),
                        "risk_score":  _safe_float(src.get("risk_score")),
                        "risk_level":  _flatten(src.get("risk_level")),
                    })
            except Exception as e:
                pass  # kNN optional — don't fail the endpoint

        return {
            "patient_id":       patient_id,
            "risk_score":       own_score,
            "risk_level":       own_level,
            "percentile":       percentile,
            "percentile_badge": _percentile_badge(percentile),
            "similar_patients": similar,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Utilities ─────────────────────────────────────────────────
def _risk_label(score: float) -> str:
    if score >= 80: return "CRITICAL"
    if score >= 60: return "HIGH"
    if score >= 40: return "ELEVATED"
    if score >= 20: return "MODERATE"
    return "LOW"

def _percentile_badge(pct: int) -> str:
    if pct >= 90: return "Top 10% highest risk"
    if pct >= 75: return "Above average risk"
    if pct >= 50: return "Moderate risk"
    if pct >= 25: return "Below average risk"
    return "Low risk"