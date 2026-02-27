# backend/api/esql.py
from fastapi import APIRouter
from pydantic import BaseModel
import time, os, httpx
from datetime import datetime, timezone
from core.elasticsearch_client import get_es_client

router    = APIRouter()
es_client = get_es_client()

class EsqlRequest(BaseModel):
    query: str
    limit: int = 100

# ── Shared function (imported by other modules) ───────────────
def run_esql_query(query: str) -> dict:
    t0 = time.monotonic()
    try:
        resp      = es_client.client.esql.query(body={"query": query})
        columns   = [{"name": c["name"], "type": c["type"]} for c in resp.get("columns", [])]
        values    = resp.get("values", [])
        col_names = [c["name"] for c in columns]
        rows      = [dict(zip(col_names, row)) for row in values]
        return {"status": "ok", "columns": columns, "rows": rows,
                "row_count": len(rows), "ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e), "rows": [], "columns": [], "ms": 0}


@router.get("/health")
async def health_check():
    try:
        t0  = time.monotonic()
        ok  = es_client.client.ping()
        cnt = es_client.count("lab-results")
        return {
            "status": "healthy",
            "elasticsearch": "connected" if ok else "disconnected",
            "lab_results_count": cnt,
            "mcp_enabled": bool(os.getenv("ELASTIC_API_KEY") and os.getenv("ELASTIC_MCP_URL")),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.post("/api/esql/run")
async def run_esql(req: EsqlRequest):
    query = req.query.strip()
    if "| limit" not in query.lower():
        query += f"\n| LIMIT {req.limit}"
    result = run_esql_query(query)
    return {
        "status": result["status"], "query": query,
        "columns": result.get("columns", []), "rows": result.get("rows", []),
        "row_count": result.get("row_count", 0), "ms": result.get("ms", 0),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        **({"error": result["error"]} if result["status"] == "error" else {}),
    }


@router.get("/api/mcp/discover")
async def mcp_discover():
    api_key = os.getenv("ELASTIC_API_KEY", "")
    mcp_url = os.getenv("ELASTIC_MCP_URL", "")
    if not api_key:
        return {"error": "ELASTIC_API_KEY not set"}
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "Authorization": f"ApiKey {api_key}", "kbn-xsrf": "true"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            ir = await client.post(mcp_url, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "labiq", "version": "1.0"}}})
            tr = await client.post(mcp_url, headers=headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools     = tr.json().get("result", {}).get("tools", [])
        our_tools = [t for t in tools if any(
            k in t.get("name", "") for k in ("patient","abnormal","critical","recent","lab","alert"))]
        return {"status": "connected", "server_info": ir.json().get("result", {}),
                "total_tools": len(tools),
                "our_tools": [{"name": t["name"], "description": t.get("description","")[:120]} for t in our_tools],
                "all_tools": [t["name"] for t in tools]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}