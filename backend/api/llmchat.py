# backend/api/llmchat.py
# Groq LLM <-> Kibana MCP
# Fixes vs old version:
#   1. SKIP_TOOLS + SKIP_PREFIXES blocks ALL platform_core_ tools
#   2. _scrub() post-processes final response to remove any leaked tool names
#   3. Trend: "trend" key holds the list, "visits" key is an int count — handled correctly
#   4. Null args: Groq sends arguments=null → default to {}
#   5. Patient ID: PAT-001 → PAT_001 normalized at entry
#   6. Hard block inside execution loop, not just in to_groq_tools
#   7. results/biomarkers key fallback chain handles both endpoint shapes

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict
import os, logging, httpx, time, uuid, json, asyncio, re
from groq import AsyncGroq

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Tools to never expose or call ─────────────────────────────
SKIP_TOOLS = {
    "platform_core_product_documentation",
    "platform_core_integration_knowledge",
    "platform_core_cases",
    "platform_core_get_workflow_execution_status",
    "platform_core_search",
    "platform_core_get_document_by_id",
    "platform_core_create_case",
    "platform_core_update_case",
    "platform_core_get_alerts",
    "platform_core_get_asset",
    "platform_core_index_explorer",
}
SKIP_PREFIXES = ("platform_core_", "platform_integration_")

# ── Env ────────────────────────────────────────────────────────
def _elastic_key() -> str: return os.getenv("ELASTIC_API_KEY", "")
def _mcp_url()     -> str: return os.getenv("ELASTIC_MCP_URL", "")
def _groq_key()    -> str: return os.getenv("GROQ_API_KEY", "")
def _groq_model()  -> str: return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
def _kibana_base() -> str: return _mcp_url().replace("/api/agent_builder/mcp", "").rstrip("/")
def _api_base()    -> str: return os.getenv("LABIQ_API_URL", "http://localhost:8000")

# ── Safe helpers ───────────────────────────────────────────────
def _n(v, default=0):
    if v is None: return default
    try: return type(default)(v)
    except (TypeError, ValueError): return default

def _s(v, default="?"):
    if v is None: return default
    s = str(v).strip()
    return s if s else default

def _flat(v) -> str:
    """Normalize ES text field — may return list or string."""
    if v is None: return ""
    if isinstance(v, list): return str(v[0]).strip() if v else ""
    return str(v).strip()


# ── MCP ────────────────────────────────────────────────────────
def _mcp_headers() -> dict:
    return {
        "Authorization": f"ApiKey {_elastic_key()}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        "kbn-xsrf":      "true",
    }

async def _mcp(method: str, params: dict, client: httpx.AsyncClient) -> dict:
    r = await client.post(
        _mcp_url(), headers=_mcp_headers(), timeout=30,
        json={"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params},
    )
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"MCP error: {body['error']}")
    return body.get("result", {})

async def mcp_initialize(c):
    return await _mcp("initialize", {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "labiq", "version": "1.0"},
    }, c)

async def mcp_list_tools(c):
    return (await _mcp("tools/list", {}, c)).get("tools", [])

async def mcp_call_tool(name: str, args: dict, c: httpx.AsyncClient) -> str:
    result  = await _mcp("tools/call", {"name": name, "arguments": args}, c)
    content = result.get("content", [])
    if isinstance(content, list):
        return "\n".join(x.get("text", json.dumps(x)) for x in content if isinstance(x, dict))
    return str(result)

def _sanitize_schema(s: dict) -> dict:
    REMOVE = {"$schema", "additionalProperties"}
    def clean(o):
        if not isinstance(o, dict): return o
        return {k: clean(v) for k, v in o.items() if k not in REMOVE}
    c = clean(s)
    if "type"       not in c: c["type"]       = "object"
    if "properties" not in c: c["properties"] = {}
    return c

def to_groq_tools(tools: list) -> list:
    out = []
    for t in tools:
        name = t["name"]
        if name in SKIP_TOOLS: continue
        if any(name.startswith(p) for p in SKIP_PREFIXES): continue
        out.append({"type": "function", "function": {
            "name":        name,
            "description": (t.get("description") or "")[:120],
            "parameters":  _sanitize_schema(t.get("inputSchema", {"type": "object", "properties": {}})),
        }})
    return out


# ── REST fetch ─────────────────────────────────────────────────
async def _fetch(url: str, c: httpx.AsyncClient) -> dict:
    try:
        r = await c.get(url, timeout=5.0)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        logger.debug(f"fetch {url}: {e}")
        return {}


# ── Clinical pattern detection ─────────────────────────────────
def _detect_patterns(results: list) -> list:
    val: Dict[str, float] = {}
    for r in results:
        name = (r.get("test_name") or r.get("name") or "").lower()
        try: val[name] = float(r.get("value") or r.get("latest") or 0)
        except: pass

    def g(keys) -> Optional[float]:
        for k in ([keys] if isinstance(keys, str) else keys):
            for n, v in val.items():
                if k in n: return v
        return None

    tg  = g("triglyceride"); hdl = g("hdl");         ldl = g("ldl")
    glc = g("glucose");      hba = g(["hba1c","a1c"])
    cr  = g("creatinine");   egf = g(["egfr","gfr"])
    alt = g("alt");          ast = g("ast")
    hgb = g(["hemoglobin","haemoglobin"])
    tsh = g("tsh");          crp = g(["c-reactive","crp"])
    vd  = g(["vitamin d","25-oh"]); b12 = g(["b12","cobalamin"])
    ua  = g("uric acid");    k   = g("potassium"); na = g("sodium")
    alb = g("albumin");      fer = g("ferritin")
    tc  = g(["total cholesterol","cholesterol, total"])

    out = []

    # Metabolic syndrome
    met = sum([bool(tg and tg>150), bool(hdl and hdl<40), bool(glc and glc>100)])
    if met >= 2:
        parts = []
        if tg  and tg  > 150: parts.append(f"TG {tg:.0f}")
        if hdl and hdl < 40:  parts.append(f"HDL {hdl:.0f}")
        if glc and glc > 100: parts.append(f"Glu {glc:.0f}")
        out.append(f"METABOLIC SYNDROME ({met}/3): {', '.join(parts)} — CVD+diabetes risk")

    # Lipids
    if tg and tg > 500:
        out.append(f"TG {tg:.0f} mg/dL — CRITICAL pancreatitis risk (nl<150)")
    elif tg and tg > 200:
        out.append(f"TG {tg:.0f} mg/dL — VERY HIGH (nl<150)")
    if ldl and ldl > 130:
        out.append(f"LDL {ldl:.0f} mg/dL — {'HIGH' if ldl>160 else 'BORDERLINE'} (opt<100)")
    if tc and hdl and hdl > 0 and tc/hdl > 5:
        out.append(f"TC/HDL ratio {tc/hdl:.1f} — >5 = high cardiovascular risk")

    # Glucose / diabetes
    if hba:
        if hba >= 6.5:  out.append(f"HbA1c {hba:.1f}% — DIABETES criteria met (≥6.5%)")
        elif hba >= 5.7: out.append(f"HbA1c {hba:.1f}% — PRE-DIABETES (5.7–6.4%)")
    if glc and 100 <= glc < 126 and not hba:
        out.append(f"Glucose {glc:.0f} mg/dL — IMPAIRED FASTING (pre-diabetes 100–125). Order HbA1c.")

    # Kidney
    if egf and egf < 60:
        out.append(f"eGFR {egf:.0f} — {'Stage 4-5 CKD' if egf<30 else 'Stage 3 CKD'}")
    elif cr and cr > 1.3:
        out.append(f"Creatinine {cr:.2f} — elevated, check eGFR")

    # Liver
    if alt and alt > 40:
        out.append(f"ALT {alt:.0f} U/L — {'severe injury' if alt>200 else 'elevated'} (nl<40)")
    if ast and alt and alt > 0 and ast/alt > 2 and ast > 40:
        out.append(f"AST/ALT {ast/alt:.1f} — alcoholic hepatitis pattern")

    # Blood
    if hgb and hgb < 12:
        out.append(f"Hgb {hgb:.1f} g/dL — {'severe anemia' if hgb<8 else 'anemia'}")

    # Thyroid
    if tsh:
        if tsh > 10:    out.append(f"TSH {tsh:.1f} — overt hypothyroidism")
        elif tsh > 4:   out.append(f"TSH {tsh:.1f} — subclinical hypothyroidism")
        elif tsh < 0.4: out.append(f"TSH {tsh:.2f} — possible hyperthyroidism")

    # Others
    if crp and crp > 3:  out.append(f"CRP {crp:.1f} mg/L — {'acute infection' if crp>10 else 'chronic inflammation'}")
    if vd  and vd  < 20: out.append(f"Vit D {vd:.0f} ng/mL — deficient (nl>30)")
    if b12 and b12 < 300: out.append(f"B12 {b12:.0f} pg/mL — {'deficient' if b12<200 else 'borderline'}")
    if ua  and ua  > 7.2: out.append(f"Uric acid {ua:.1f} — gout risk")
    if k   and (k>5.5 or k<3.0): out.append(f"K {k:.1f} mEq/L — {'HIGH cardiac risk' if k>5.5 else 'LOW'}")
    if na  and (na<130 or na>150): out.append(f"Na {na:.0f} — {'hyponatremia' if na<130 else 'hypernatremia'} urgent")
    if fer and fer < 15: out.append(f"Ferritin {fer:.0f} — iron depleted")
    if alb and alb < 3.5: out.append(f"Albumin {alb:.1f} — low")

    return out


def _borderline_values(results: list) -> list:
    out = []
    for r in results:
        if r.get("is_abnormal") or (r.get("severity") or "").lower() in ("critical","abnormal"):
            continue
        try:
            v    = float(r.get("value") or r.get("latest") or 0)
            rmax = float(r.get("reference_max") or r.get("ref_max") or 0)
            if rmax > 0:
                pct = (v / rmax) * 100
                if pct >= 75:
                    out.append((pct, r.get("test_name") or r.get("name","?"), v, r.get("unit",""), rmax))
        except: pass
    out.sort(reverse=True)
    return out[:4]


# ── Context builder ────────────────────────────────────────────
async def _build_context(patient_id: str) -> str:
    patient_id = patient_id.replace("-", "_").upper().strip()
    try:
        base = _api_base()
        async with httpx.AsyncClient(timeout=6.0) as c:
            summary, bio, trend = await asyncio.gather(
                _fetch(f"{base}/api/patients/{patient_id}/summary",    c),
                _fetch(f"{base}/api/patients/{patient_id}/biomarkers", c),
                _fetch(f"{base}/api/patients/{patient_id}/risk-trend", c),
            )

        logger.info(
            f"CTX[{patient_id}] "
            f"summary_keys={list(summary.keys())} risk={summary.get('risk_score')} "
            f"bio_biomarkers={len(bio.get('biomarkers') or [])} bio_results={len(bio.get('results') or [])} "
            f"trend_visits_int={trend.get('visits') if isinstance(trend,dict) else None} "
            f"trend_list_len={len(trend.get('trend') or []) if isinstance(trend,dict) else 0}"
        )

        lines = []

        # ── Risk header ────────────────────────────────────────
        risk  = _n(summary.get("risk_score"), 0)
        level = _flat(summary.get("risk_level")) or "unknown"
        date  = _s(summary.get("latest_test_date") or summary.get("test_date") or
                   summary.get("last_test_date"), "unknown")[:10]
        abn   = _n(summary.get("total_abnormal") or summary.get("abnormal"), 0)
        crit  = _n(summary.get("total_critical") or summary.get("critical"), 0)
        total = _n(summary.get("total_tests") or summary.get("total_panels"), 0)
        lines.append(f"PT:{patient_id} Risk:{risk}/100({level}) Date:{date} Panels:{total} Abn:{abn} Crit:{crit}")

        # ── Biomarker results ──────────────────────────────────
        # biomarkers endpoint: {biomarkers:[{name,latest,...}], results:[{test_name,value,...}]}
        # summary endpoint:    {results:[{test_name,value,...}]}
        results = (
            bio.get("results") or bio.get("biomarkers") or
            summary.get("results") or summary.get("biomarkers") or []
        )
        if not results:
            for p in (bio.get("panels") or []):
                if p.get("results"): results = p["results"]; break

        if results:
            flagged = [r for r in results
                       if r.get("is_abnormal") or r.get("is_critical")
                       or (r.get("severity") or "").lower() in ("critical","abnormal")]

            if flagged:
                lines.append("FLAGGED:")
                for r in sorted(flagged, key=lambda x: 0 if (x.get("severity") or "").lower()=="critical" else 1):
                    icon  = "🔴" if (r.get("severity") or "").lower()=="critical" else "🟡"
                    name  = r.get("test_name") or r.get("name", "?")
                    val   = r.get("value") or r.get("latest", "?")
                    unit  = r.get("unit", "")
                    rmin  = r.get("reference_min") or r.get("ref_min")
                    rmax  = r.get("reference_max") or r.get("ref_max")
                    ref   = f"[{rmin}-{rmax}]" if rmin and rmax else (f"[<{rmax}]" if rmax else "")
                    dev   = r.get("deviation_pct")
                    devs  = f" {_n(dev):+.0f}%" if dev is not None and dev != 0 else ""
                    lines.append(f"  {icon}{name}:{val}{unit}{ref}{devs}")

            patterns = _detect_patterns(results)
            if patterns:
                lines.append("PATTERNS:")
                for p in patterns:
                    lines.append(f"  !{p}")

            if not flagged and not patterns:
                border = _borderline_values(results)
                if border:
                    lines.append("BORDERLINE(watch):")
                    for pct, name, val, unit, rmax in border:
                        lines.append(f"  {name}:{val}{unit} at {pct:.0f}% of max {rmax}")
                else:
                    lines.append("ALL_NORMAL: all values within reference ranges")
        else:
            lines.append("VALUES:not_available — no results in latest panel")

        # ── Visit trend ────────────────────────────────────────
        # risk-trend returns: {visits:4 (int), trend:[{date,risk_score,...}], direction, pct_change}
        # "visits" key = integer count, NOT the list
        # "trend"  key = the actual list of visit dicts
        visits = []
        if isinstance(trend, dict):
            v = trend.get("trend")
            if isinstance(v, list) and v and isinstance(v[0], dict):
                visits = v

        if len(visits) >= 2:
            direction  = _s(trend.get("direction"), "stable")
            pct_change = _n(trend.get("pct_change"), 0.0)
            first_s    = _n(trend.get("first_score"), 0)
            last_s     = _n(trend.get("last_score"), 0)
            lines.append(f"TREND({len(visits)} visits,{direction},{pct_change:+.1f}%,risk {first_s}→{last_s}):")
            for v in visits:
                d    = _s(v.get("date") or v.get("test_date"), "?")[:10]
                rs   = _n(v.get("risk_score"), 0)
                rl   = _flat(v.get("risk_level"))
                ab   = _n(v.get("abnormal"), 0)
                cr   = _n(v.get("critical"), 0)
                icon = "🔴" if cr > 0 else "🟡" if ab > 0 else "✅"
                lines.append(f"  {icon}{d}: risk={rs}({rl}) abn={ab} crit={cr}")
        elif len(visits) == 1:
            v = visits[0]
            lines.append(f"VISITS:1 — only {_s(v.get('date') or v.get('test_date'))[:10]} on record.")
        elif isinstance(trend, dict) and _n(trend.get("visits"), 0) >= 2:
            lines.append(f"VISITS:{trend['visits']} panels recorded — history available on request")
        else:
            lines.append("VISITS:no_history — first panel or history unavailable")

        ctx = "\n".join(lines)
        logger.info(f"CTX[{patient_id}] {len(ctx)} chars ~{len(ctx)//4} tokens")
        return ctx

    except Exception as e:
        logger.warning(f"CTX[{patient_id}] failed: {e}")
        return f"PT:{patient_id} Risk:unknown\nVALUES:not_available\nVISITS:no_history"


# ── Tool name scrubber ─────────────────────────────────────────
def _scrub(text: str, groq_tools: list) -> str:
    """Remove tool names that Groq narrates into its response."""
    if not text: return text

    names = set()
    for t in groq_tools:
        n = t.get("function", {}).get("name", "")
        if n:
            names.add(n)
            names.add(n.replace("_", " "))

    # Always scrub these regardless of tool list
    names.update({
        "platform core search", "platform_core_search",
        "platform core get document by id", "platform_core_get_document_by_id",
        "platform core index explorer", "platform_core_index_explorer",
        "rank patients by risk", "rank_patients_by_risk",
        "get patient summary", "get_patient_summary",
        "lab timeline", "lab_timeline",
        "find abnormal results", "find_abnormal_results",
        "count critical flags", "count_critical_flags",
        "get recent test dates", "get_recent_test_dates",
        "critical patients alert", "critical_patients_alert",
    })

    clean = []
    for line in text.splitlines():
        low = line.lower().strip()
        if any(low == n.lower() for n in names):
            continue
        if re.match(r"^(i (will|am|'ll) (use|call|query|run|check)|using tool|calling|fetching via)\b", low):
            continue
        clean.append(line)

    result = "\n".join(clean).strip()
    for n in sorted(names, key=len, reverse=True):
        result = re.sub(re.escape(n), "", result, flags=re.IGNORECASE)
    result = re.sub(r"  +", " ", result)
    result = re.sub(r" ([,.])", r"\1", result)
    return result.strip()


# ── Schemas ────────────────────────────────────────────────────
class LlmRequest(BaseModel):
    message: str
    patient_id: str = "PAT001"
    conversation_history: Optional[List[dict]] = []

class LlmResponse(BaseModel):
    response: str
    source: str = "kibana_agent"
    tools_used: List[str] = []
    esql_query: Optional[str] = None
    reasoning_trace: Optional[List[dict]] = None
    execution_ms: Optional[int] = None
    error: Optional[str] = None


# ── Main endpoint ──────────────────────────────────────────────
@router.post("/api/llm/chat", response_model=LlmResponse)
async def llm_chat(req: LlmRequest):
    t0  = time.monotonic()
    ms  = lambda: int((time.monotonic() - t0) * 1000)
    trace, tools_used, esql_found, final_text = [], [], None, ""

    if not _elastic_key() or not _mcp_url():
        return LlmResponse(response="ELASTIC_API_KEY or ELASTIC_MCP_URL not set.", source="error", execution_ms=ms())
    if not _groq_key():
        return LlmResponse(response="⚠️ GROQ_API_KEY not set in .env.", source="error", execution_ms=ms())

    # Normalize PAT-001 → PAT_001
    req.patient_id = req.patient_id.replace("-", "_").upper().strip()
    logger.info(f"[{req.patient_id}] {_groq_model()} — {req.message[:60]}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:

            # 1 — Context
            trace.append({"step": "Building compact ES context"})
            ctx = await _build_context(req.patient_id)
            trace.append({"step": f"Context ready ({len(ctx)} chars)"})

            # 2 — MCP tools
            trace.append({"step": "MCP init + tool list"})
            await mcp_initialize(http)
            mcp_tools  = await mcp_list_tools(http)
            groq_tools = to_groq_tools(mcp_tools)
            logger.info(f"{len(groq_tools)} tools exposed to Groq")

            # 3 — System prompt
            system = (
                f"You are LabIQ, a clinical lab analyst. Patient: {req.patient_id}.\n"
                f"LAB DATA:\n{ctx}\n\n"
                f"RESPONSE RULES:\n"
                f"- Quote exact values with units: 'Triglycerides 955 mg/dL'\n"
                f"- Interpret EVERY flagged value — what does this number mean clinically?\n"
                f"  VISITS:no_history or VISITS:1 = first recorded panel, no prior data.\n"
                f"- Organize: Current Values → Trend → Clinical Meaning → Recommendations\n"
                f"- Give exactly 3 specific recommendations tailored to these exact values\n"
                f"- NEVER mention tool names, function names, system names, or database names\n"
                f"- NEVER say MCP, Elasticsearch, ES|QL, Kibana, API, or any technical term\n"
                f"- If a value is missing say 'not recorded' — never explain technically why\n"
                f"- Max 350 words. Be specific to this patient's actual numbers."
            )

            recent_history = [
                {"role": h["role"], "content": h["content"]}
                for h in (req.conversation_history or [])[-4:]
                if h.get("role") in ("user", "assistant")
            ]

            messages = [
                {"role": "system",  "content": system},
                *recent_history,
                {"role": "user",    "content": req.message},
            ]

            # 4 — Agentic loop
            groq = AsyncGroq(api_key=_groq_key())
            for i in range(3):
                trace.append({"step": f"LLM turn {i+1}"})
                resp = await groq.chat.completions.create(
                    model=_groq_model(), messages=messages,
                    tools=groq_tools, tool_choice="auto",
                    max_tokens=600, temperature=0.15,
                )
                msg = resp.choices[0].message

                if not msg.tool_calls:
                    final_text = msg.content or ""
                    trace.append({"step": "Response ready"})
                    break

                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tname = tc.function.name

                    # Hard block — never call skipped tools even if Groq requests them
                    if tname in SKIP_TOOLS or any(tname.startswith(p) for p in SKIP_PREFIXES):
                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": "No additional data available."})
                        trace.append({"step": f"BLOCKED {tname}"})
                        continue

                    tools_used.append(tname)
                    trace.append({"step": f"MCP→{tname}", "tool": tname})

                    # Fix: Groq sends arguments=null for no-param tools
                    raw_args = tc.function.arguments
                    try:
                        args = json.loads(raw_args) if raw_args and raw_args.strip() not in ("null","None","") else {}
                        if not isinstance(args, dict): args = {}
                    except Exception:
                        args = {}

                    # Inject patient_id for tools that accept it
                    args.setdefault("patient_id", req.patient_id)

                    try:
                        raw = await mcp_call_tool(tname, args, http)
                        raw = raw[:1200] if len(raw) > 1200 else raw
                        if "esql" in tname.lower() and not esql_found:
                            esql_found = raw[:400]
                        trace.append({"step": f"✓{tname}", "rows": len(raw.splitlines())})
                        tool_result = raw
                    except Exception as e:
                        logger.error(f"Tool {tname}: {e}")
                        trace.append({"step": f"✗{tname}", "error": str(e)})
                        tool_result = "No data returned."
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})
            else:
                trace.append({"step": "Max turns — forcing answer"})

            # 5 — Force answer if needed
            if not final_text:
                trace.append({"step": "Final pass"})
                sr = await groq.chat.completions.create(
                    model=_groq_model(), messages=messages,
                    tools=groq_tools, tool_choice="none",
                    max_tokens=600, temperature=0.15,
                )
                final_text = sr.choices[0].message.content or ""

            # 6 — Scrub leaked tool names from response
            final_text = _scrub(final_text, groq_tools)

        return LlmResponse(
            response=final_text or "No response generated.",
            source="kibana_agent",
            tools_used=list(dict.fromkeys(tools_used)),
            esql_query=esql_found,
            reasoning_trace=trace,
            execution_ms=ms(),
        )

    except Exception as e:
        logger.exception("Agentic loop error")
        return LlmResponse(response=f"⚠️ {e}", source="error",
                           reasoning_trace=trace, execution_ms=ms(), error=str(e))


# ── MCP discover ───────────────────────────────────────────────
@router.get("/api/mcp/discover")
async def mcp_discover():
    if not _elastic_key() or not _mcp_url():
        return {"status": "unconfigured", "total_tools": 0}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            await mcp_initialize(c)
            tools = await mcp_list_tools(c)
            return {
                "status": "connected", "total_tools": len(tools),
                "our_tools": [{"name": t["name"], "description": t.get("description","")} for t in tools],
            }
    except Exception as e:
        return {"status": "disconnected", "total_tools": 0, "error": str(e)}


@router.get("/api/llm/status")
async def llm_status():
    base = _kibana_base()
    if not base: return {"status": "unconfigured"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{base}/api/status", headers=_mcp_headers())
            return {"status": "reachable" if r.status_code < 400 else "error",
                    "code": r.status_code, "model": _groq_model(),
                    "groq": "ok" if _groq_key() else "MISSING"}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}