# backend/api/alerts.py
from fastapi import APIRouter
from datetime import datetime, timezone
from core.elasticsearch_client import get_es_client
from api.esql import run_esql_query

router    = APIRouter()
es_client = get_es_client()


@router.get("/api/alerts/feed")
async def get_alert_feed(patient_id: str = "PAT001"):
    esql = f"""FROM lab-results
| WHERE patient_id == "{patient_id}"
| SORT test_date DESC
| LIMIT 5
| KEEP test_date, test_type, abnormal_flags, critical_flags""".strip()

    result = run_esql_query(esql)
    alerts = []

    for row in result.get("rows", []):
        date     = str(row.get("test_date", ""))[:10]
        critical = row.get("critical_flags")
        abnormal = row.get("abnormal_flags")
        if critical:
            alerts.append({"level": "critical", "title": "Critical Values Detected",
                           "detail": str(critical), "date": date, "icon": "🚨"})
        if abnormal:
            alerts.append({"level": "warning", "title": "Abnormal Results",
                           "detail": str(abnormal), "date": date, "icon": "⚠️"})

    try:
        resp = es_client.client.search(index="lab-results", body={
            "query": {"term": {"patient_id.keyword": patient_id}},
            "sort": [{"test_date": "desc"}], "size": 1, "_source": True,
        })
        hits = resp["hits"]["hits"]
        if hits:
            for r in hits[0]["_source"].get("results", []):
                name = r.get("test_name", "")
                val  = r.get("value", 0) or 0
                if "Triglycerides" in name and val > 500:
                    alerts.insert(0, {"level": "critical", "title": "⚡ Pancreatitis Risk",
                                      "detail": f"Triglycerides {val} mg/dL — dangerously high (normal <150)",
                                      "date": "latest", "icon": "🚨"})
                elif "HDL" in name and val < 30:
                    alerts.insert(0, {"level": "critical", "title": "⚡ Critical Low HDL",
                                      "detail": f"HDL {val} mg/dL — critically low (normal >50)",
                                      "date": "latest", "icon": "🚨"})
                elif "Cholesterol" in name and "HDL" not in name and val > 240:
                    alerts.insert(0, {"level": "warning", "title": "High Cholesterol",
                                      "detail": f"Total Cholesterol {val} mg/dL (normal <200)",
                                      "date": "latest", "icon": "⚠️"})
    except Exception:
        pass

    return {"patient_id": patient_id, "alerts": alerts[:10], "esql_query": esql,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "esql_ms": result.get("ms", 0)}