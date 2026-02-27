# backend/api/chat.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import os, logging, time
from datetime import datetime, timezone

from core.elasticsearch_client import get_es_client
from tools.lab_analyzer import LabAnalyzer
from tools.knowledge_search import KnowledgeSearcher

router    = APIRouter()
es_client = get_es_client()
analyzer  = LabAnalyzer(es_client.client)
knowledge = KnowledgeSearcher(es_client.client)
logger    = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    message: str
    patient_id: str = "PAT001"
    conversation_history: Optional[List[dict]] = []

class ChatResponse(BaseModel):
    response: str
    tools_used: List[str] = []
    esql_query: Optional[str] = None
    data: Optional[dict] = None
    source: str = "fallback"
    reasoning_trace: Optional[List[dict]] = []
    execution_ms: Optional[int] = None


# ── ES|QL direct runner ───────────────────────────────────────
def _run_tool_locally(tool_name: str, patient_id: str) -> dict:
    from api.esql import run_esql_query
    queries = {
        "get_patient_summary": f"""
FROM lab-results
| WHERE patient_id == "{patient_id}"
| STATS total_tests = COUNT(*), first_test = MIN(test_date), last_test = MAX(test_date)
""",
        "get_recent_test_dates": f"""
FROM lab-results
| WHERE patient_id == "{patient_id}"
| SORT test_date DESC
| LIMIT 5
| KEEP test_date, test_type, lab_name
""",
        "count_critical_flags": f"""
FROM lab-results
| WHERE patient_id == "{patient_id}"
| STATS
    total_panels = COUNT(*),
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical = COUNT(*) WHERE critical_flags IS NOT NULL
""",
        "rank_patients_by_risk": """
FROM lab-results
| STATS
    total_panels = COUNT(*),
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical = COUNT(*) WHERE critical_flags IS NOT NULL
  BY patient_id
| EVAL risk_score = critical * 3 + abnormal
| SORT risk_score DESC
""",
    }
    query = queries.get(tool_name, "")
    if not query:
        return {"rows": [], "columns": [], "esql": ""}
    result = run_esql_query(query.strip())
    return {
        "rows":    result.get("rows", []),
        "columns": result.get("columns", []),
        "esql":    query.strip(),
    }


# ── DSL search for actual nested values ──────────────────────
def _get_abnormal_values(patient_id: str) -> str:
    """
    ES|QL cannot access nested results[] array.
    Use DSL to get actual test values with severity.
    """
    try:
        resp = es_client.client.search(index="lab-results", body={
            "query": {"term": {"patient_id.keyword": patient_id}},
            "sort": [{"test_date": "desc"}],
            "size": 5,
            "_source": True,
        })
        hits = resp["hits"]["hits"]
        if not hits:
            return "No results found."

        lines = []
        seen_dates = set()

        for hit in hits:
            src  = hit["_source"]
            date = str(src.get("test_date", ""))[:10]
            if date in seen_dates:
                continue
            seen_dates.add(date)

            results  = src.get("results", [])
            abnormal = [
                r for r in results
                if r.get("is_abnormal") or r.get("severity") in ("critical", "abnormal")
            ]
            if not abnormal:
                continue

            lines.append(f"\n**📅 {date}**")
            for r in abnormal:
                name     = r.get("test_name", "Unknown")
                val      = r.get("value", "N/A")
                unit     = r.get("unit", "")
                severity = r.get("severity", "abnormal")
                ref_min  = r.get("reference_min")
                ref_max  = r.get("reference_max")

                if ref_min is not None and ref_max is not None:
                    ref_str = f" | ref: {ref_min}–{ref_max}"
                elif ref_max is not None:
                    ref_str = f" | ref: <{ref_max}"
                elif ref_min is not None:
                    ref_str = f" | ref: >{ref_min}"
                else:
                    ref_str = ""

                icon = "🔴" if severity == "critical" else "🟡"
                lines.append(f"{icon} **{name}**: {val} {unit}{ref_str}")

        return "\n".join(lines) if lines else "✅ No abnormal values found in recent panels."

    except Exception as e:
        return f"Error fetching values: {e}"


def _get_latest_values(patient_id: str) -> str:
    """Get all values from the most recent panel."""
    try:
        resp = es_client.client.search(index="lab-results", body={
            "query": {"term": {"patient_id.keyword": patient_id}},
            "sort": [{"test_date": "desc"}],
            "size": 1,
            "_source": True,
        })
        hits = resp["hits"]["hits"]
        if not hits:
            return "No results found."

        src     = hits[0]["_source"]
        date    = str(src.get("test_date", ""))[:10]
        results = src.get("results", [])

        lines = [f"**Most Recent Panel — {date}**\n"]
        for r in results[:12]:
            name     = r.get("test_name", "")
            val      = r.get("value", "N/A")
            unit     = r.get("unit", "")
            severity = r.get("severity", "normal")
            is_abn   = r.get("is_abnormal", False)
            icon = "🔴" if severity == "critical" else "🟡" if is_abn else "✅"
            lines.append(f"{icon} **{name}**: {val} {unit}")

        abn  = src.get("abnormal_flags", [])
        crit = src.get("critical_flags", [])
        if crit:
            lines.append(f"\n🚨 **Critical:** {', '.join(crit) if isinstance(crit, list) else crit}")
        if abn:
            lines.append(f"⚠️ **Abnormal:** {', '.join(abn) if isinstance(abn, list) else abn}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ── Tool picker ───────────────────────────────────────────────
def _pick_tool(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in ("summary", "overview", "how many", "total")):
        return "get_patient_summary"
    if any(k in msg for k in ("abnormal", "flag", "out of range")):
        return "find_abnormal_results"
    if any(k in msg for k in ("critical", "urgent", "danger")):
        return "count_critical_flags"
    if any(k in msg for k in ("latest", "recent", "show", "result", "value")):
        return "get_latest_values"
    if any(k in msg for k in ("rank", "worst", "attention", "all patients")):
        return "rank_patients_by_risk"
    if any(k in msg for k in ("date", "when", "last test", "history")):
        return "get_recent_test_dates"
    return "get_patient_summary"


def _format_rows(tool_name: str, result: dict, patient_id: str) -> str:
    titles = {
        "get_patient_summary":   "📋 Patient Summary",
        "count_critical_flags":  "🚨 Critical & Abnormal Count",
        "get_recent_test_dates": "📅 Recent Tests",
        "rank_patients_by_risk": "🏥 Patient Risk Ranking",
    }
    title = titles.get(tool_name, "📊 Results")
    rows  = result.get("rows", [])
    if not rows:
        return f"{title} (Patient: {patient_id})\n\nNo results found."
    lines = [f"{title} (Patient: **{patient_id}**)\n"]
    for row in rows:
        parts = []
        for col, val in row.items():
            if val is None:
                val = "N/A"
            if "date" in col and isinstance(val, str) and "T" in val:
                val = val[:10]
            parts.append(f"{col}: {val}")
        lines.append("• " + " | ".join(parts))
    return "\n".join(lines)


# ── Main chat endpoint ────────────────────────────────────────
@router.post("/api/chat", response_model=ChatResponse)
async def chat(msg: ChatMessage):
    t0, trace = time.monotonic(), []
    tool_name = _pick_tool(msg.message)

    trace.append({"step": "tool_selected", "tool": tool_name,
                  "ts": datetime.now(timezone.utc).isoformat()})

    # Tools that use DSL (can access nested results[] values)
    if tool_name == "find_abnormal_results":
        response_text = _get_abnormal_values(msg.patient_id)
        esql = f'FROM lab-results | WHERE patient_id == "{msg.patient_id}" | KEEP abnormal_flags, critical_flags'
        trace.append({"step": "dsl_executed", "ts": datetime.now(timezone.utc).isoformat()})
        return ChatResponse(
            response=response_text,
            tools_used=["find_abnormal_results"],
            esql_query=esql,
            source="esql_direct",
            reasoning_trace=trace,
            execution_ms=int((time.monotonic() - t0) * 1000),
        )

    if tool_name == "get_latest_values":
        response_text = _get_latest_values(msg.patient_id)
        esql = f'FROM lab-results | WHERE patient_id == "{msg.patient_id}" | SORT test_date DESC | LIMIT 1'
        trace.append({"step": "dsl_executed", "ts": datetime.now(timezone.utc).isoformat()})
        return ChatResponse(
            response=response_text,
            tools_used=["get_latest_values"],
            esql_query=esql,
            source="esql_direct",
            reasoning_trace=trace,
            execution_ms=int((time.monotonic() - t0) * 1000),
        )

    # Tools that use ES|QL
    try:
        result = _run_tool_locally(tool_name, msg.patient_id)
        trace.append({"step": "esql_executed", "rows": len(result.get("rows", [])),
                      "ts": datetime.now(timezone.utc).isoformat()})
        rows = result.get("rows", [])
        if rows:
            return ChatResponse(
                response=_format_rows(tool_name, result, msg.patient_id),
                tools_used=[tool_name],
                esql_query=result.get("esql"),
                source="esql_direct",
                reasoning_trace=trace,
                execution_ms=int((time.monotonic() - t0) * 1000),
            )
    except Exception as e:
        logger.warning(f"ES|QL failed: {e}")
        trace.append({"step": "esql_error", "error": str(e),
                      "ts": datetime.now(timezone.utc).isoformat()})

    # Local analyzer fallback
    resp = await _local_fallback(msg, trace)
    resp.execution_ms = int((time.monotonic() - t0) * 1000)
    return resp


# ── Local fallback ────────────────────────────────────────────
async def _local_fallback(msg: ChatMessage, trace: list) -> ChatResponse:
    message = msg.message.lower()
    tools_used, response_text, esql_query, data = [], "", None, None
    result: dict = {}

    if any(k in message for k in ("trend", "changing", "over time")):
        result = analyzer.analyze_all_trends(msg.patient_id)
        tools_used.append("analyze_all_trends")
        if result["status"] == "success":
            concerning = result.get("concerning_trends", [])
            lines = "\n".join(
                f"• **{t['test_name']}**: {t['trend_direction']} ({t['percent_change']:+.1f}%)"
                for t in concerning[:5]) if concerning else "All values stable ✓"
            response_text = f"**Lab Trends:**\n\n{lines}\n\n{result['summary']}"
        else:
            response_text = result.get("message", "Could not analyse trends.")
        esql_query = result.get("esql_query")

    elif any(k in message for k in ("what", "explain", "mean", "why")):
        result = knowledge.search(msg.message)
        tools_used.append("knowledge_base")
        if result["status"] == "success" and result.get("results"):
            top = result["results"][0]
            response_text = f"{top['answer']}\n\n_Source: {top['source']}_"
        else:
            response_text = "I don't have a specific explanation for that."

    elif any(k in message for k in ("summary", "overview")):
        result = analyzer.get_patient_summary(msg.patient_id)
        tools_used.append("get_patient_summary")
        if result["status"] == "success":
            response_text = (
                f"**Patient Summary — {msg.patient_id}**\n\n"
                f"📋 Total: {result['total_tests']} panels\n"
                f"⚠️ Abnormal: {result['abnormal_tests']}\n"
                f"🚨 Critical: {result['critical_tests']}\n\n"
                f"📅 {str(result.get('first_test_date',''))[:10]} → "
                f"{str(result.get('last_test_date',''))[:10]}"
            )
        else:
            response_text = "No lab history found."
        esql_query = result.get("esql_query")
    else:
        response_text = (
            "I can help with:\n\n"
            "• **Show latest results** — actual test values\n"
            "• **Abnormal results** — values outside reference range\n"
            "• **Lab summary** — overview stats\n"
            "• **Analyze trends** — how values change over time\n"
            "• **Find critical values** — urgent concerns\n"
            "• **Rank patients by risk** — who needs attention most\n\n"
            "What would you like to know?"
        )

    return ChatResponse(
        response=response_text, tools_used=tools_used,
        esql_query=esql_query, data=data,
        source="fallback", reasoning_trace=trace,
    )