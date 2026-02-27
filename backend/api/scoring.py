from fastapi import APIRouter, HTTPException
import logging
from core.elasticsearch_client import get_es_client
from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _similarity_label(score):
    if score >= 0.95: return "Nearly identical lab profile"
    if score >= 0.85: return "Very similar metabolic pattern"
    if score >= 0.70: return "Moderately similar profile"
    return "Dissimilar profile"

def _percentile_badge(pct):
    if pct >= 95: return "🔴 Top 5% Most Critical"
    if pct >= 90: return "🔴 Top 10% Most Critical"
    if pct >= 75: return "🟠 Top 25% High Risk"
    if pct >= 50: return "🟡 Above Average Risk"
    return "🟢 Below Average Risk"

def _score_to_priority(score):
    if score >= 8: return "IMMEDIATE"
    if score >= 4: return "URGENT"
    if score >= 2: return "MONITOR"
    return "ROUTINE"


@router.get("/api/patients/{patient_id}/similar")
def similar_patients(patient_id: str, k: int = 5):
    """
    kNN cosine similarity on dense_vector risk_vector.
    Returns k unique patients — deduplication handled in ES client
    so time-series uploads (multiple docs per patient) don't cause repeats.
    """
    try:
        es   = get_es_client()
        data = es.find_similar_patients(patient_id, k=k)
        if not data:
            return {
                "patient_id": patient_id,
                "similar":    [],
                "message":    "No risk_vector found — upload PDFs for multiple patients",
            }
        return {
            "patient_id":   patient_id,
            "method":       "knn_cosine_similarity",
            "vector_dims":  len(settings.RISK_VECTOR_FIELDS),
            "index":        "HNSW",
            "similar": [
                {
                    "patient_id":     s["patient_id"],
                    "similarity":     s["similarity"],
                    "similarity_pct": round(s["similarity"] * 100, 1),
                    "risk_score":     s["risk_score"],
                    "risk_level":     s["risk_level"],
                    "critical_flags": s.get("critical_flags", []),
                    "interpretation": _similarity_label(s["similarity"]),
                }
                for s in data
            ],
        }
    except Exception as e:
        logger.exception("similar_patients failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/patients/{patient_id}/percentile")
def patient_percentile(patient_id: str):
    """
    Percentile rank using max risk_score per patient (time-series safe).
    Each patient collapses to their peak risk via max aggregation.
    """
    try:
        es   = get_es_client()
        data = es.patient_percentile(patient_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"No data for {patient_id}")
        pct = data["percentile"]
        return {
            **data,
            "percentile_badge": _percentile_badge(pct),
            "urgency": (
                "immediate" if pct >= 90 else
                "urgent"    if pct >= 75 else
                "monitor"   if pct >= 50 else
                "routine"
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("patient_percentile failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/patients/{patient_id}/scored-panels")
def scored_panels(patient_id: str, limit: int = 10):
    """
    function_score ranked panels: critical_flags (10×) + gauss decay + field_value_factor.
    Each panel = one ES document = one lab visit.
    """
    try:
        es   = get_es_client()
        data = es.scored_patient_search(patient_id)
        panels = [
            {
                "test_date":     doc.get("test_date", "")[:10],
                "test_type":     doc.get("test_type", ""),
                "es_score":      doc.get("_score", 0),
                "risk_score":    doc.get("risk_score", 0),
                "risk_level":    doc.get("risk_level", "LOW"),
                "critical_flags":doc.get("critical_flags", []),
                "abnormal_flags":doc.get("abnormal_flags", []),
                "result_count":  len(doc.get("results", [])),
                "priority":      _score_to_priority(doc.get("_score", 0)),
            }
            for doc in data[:limit]
        ]
        return {
            "patient_id": patient_id,
            "panels":     panels,
            "note":       "Ranked by ES function_score: critical_flags (10×) + gauss decay (30d) + field_value_factor(risk_score)",
        }
    except Exception as e:
        logger.exception("scored_panels failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/population")
def population_stats():
    """ES aggregations: percentiles, terms, date_histogram, filter aggs."""
    try:
        es = get_es_client()
        return {**es.population_stats(), "powered_by": "Elasticsearch aggregations"}
    except Exception as e:
        logger.exception("population_stats failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/patients/{patient_id}/trend/{test_name}")
def biomarker_trend(patient_id: str, test_name: str):
    """date_histogram + nested aggregation across all uploaded documents."""
    try:
        es   = get_es_client()
        data = es.trending_biomarkers(patient_id, test_name)
        if not data:
            return {
                "patient_id": patient_id,
                "test_name":  test_name,
                "trend":      [],
                "message":    f"No data for {test_name}",
            }
        if len(data) >= 2:
            first, last = data[0]["avg"], data[-1]["avg"]
            pct_change  = round((last - first) / first * 100, 1) if first else 0
            direction   = "↑ Rising" if pct_change > 5 else "↓ Falling" if pct_change < -5 else "→ Stable"
        else:
            pct_change, direction = 0, "→ Stable"

        ref = settings.REFERENCE_RANGES.get(test_name, {})
        return {
            "patient_id":  patient_id,
            "test_name":   test_name,
            "trend":       data,
            "direction":   direction,
            "pct_change":  pct_change,
            "ref_min":     ref.get("min"),
            "ref_max":     ref.get("max"),
            "unit":        ref.get("unit", ""),
            "powered_by":  "ES date_histogram + nested aggregations",
        }
    except Exception as e:
        logger.exception("biomarker_trend failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/patients/{patient_id}/risk-trend")
def patient_risk_trend(patient_id: str):
    """
    Recovery/deterioration timeline — one data point per uploaded PDF.
    ES returns documents sorted by test_date ascending so the chart shows
    time progression naturally. Each doc = one real-world lab visit.
    """
    try:
        es     = get_es_client()
        points = es.patient_risk_trend(patient_id)
        if not points:
            return {"patient_id": patient_id, "trend": [], "message": "No documents found"}

        # Compute direction from first to last visit
        if len(points) >= 2:
            first_score = points[0]["risk_score"]
            last_score  = points[-1]["risk_score"]
            delta       = last_score - first_score
            direction   = "↓ Improving" if delta < -5 else "↑ Deteriorating" if delta > 5 else "→ Stable"
            pct_change  = round((delta / first_score * 100), 1) if first_score else 0
        else:
            direction, pct_change = "→ Single visit", 0

        return {
            "patient_id":  patient_id,
            "trend":       points,
            "visits":      len(points),
            "direction":   direction,
            "pct_change":  pct_change,
            "first_score": points[0]["risk_score"]  if points else 0,
            "last_score":  points[-1]["risk_score"] if points else 0,
            "powered_by":  "ES term query · sort by test_date · time-series documents",
        }
    except Exception as e:
        logger.exception("patient_risk_trend failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/patients/{patient_id}/scoring-summary")
def scoring_summary(patient_id: str):
    """Combined ES signals for LLM context injection."""
    try:
        es         = get_es_client()
        percentile = es.patient_percentile(patient_id)
        similar    = es.find_similar_patients(patient_id, k=3)
        panels     = es.scored_patient_search(patient_id)
        top_panel  = panels[0] if panels else {}

        return {
            "patient_id":        patient_id,
            "percentile":        percentile.get("percentile", 0),
            "percentile_badge":  _percentile_badge(percentile.get("percentile", 0)),
            "risk_score":        percentile.get("risk_score", 0),
            "interpretation":    percentile.get("interpretation", ""),
            "top_panel": {
                "test_date":     top_panel.get("test_date", "")[:10],
                "test_type":     top_panel.get("test_type", ""),
                "es_score":      top_panel.get("_score", 0),
                "risk_level":    top_panel.get("risk_level", "LOW"),
                "critical_flags":top_panel.get("critical_flags", []),
            },
            "similar_patients": [
                {
                    "patient_id": s["patient_id"],
                    "similarity": s["similarity"],
                    "risk_level": s["risk_level"],
                }
                for s in similar
            ],
            "powered_by": "ES kNN + function_score + aggregations",
        }
    except Exception as e:
        logger.exception("scoring_summary failed")
        raise HTTPException(status_code=500, detail=str(e))