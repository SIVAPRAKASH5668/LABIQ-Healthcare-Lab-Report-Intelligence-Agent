"""
LabIQ - Healthcare Lab Report Intelligence Agent
Main FastAPI Application
"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import AsyncElasticsearch

from core.config import settings
from api.routes import router
from api.llmchat import router as llm_router
from api.scoring import router as scoring_router

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Slack Bot Thread
# ─────────────────────────────────────────────

def _start_slack_bot():
    """
    Start the Slack bot via slack_bot.start_slack_threads().
    Only runs if SLACK_BOT_TOKEN and SLACK_APP_TOKEN are set.
    FastAPI continues normally if tokens are missing or slack-bolt not installed.
    """
    if not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("SLACK_APP_TOKEN"):
        logger.info("⚠️  Slack disabled — set SLACK_BOT_TOKEN + SLACK_APP_TOKEN in .env to enable")
        return

    # Ensure the backend directory is on sys.path so slack_bot.py can be found
    # regardless of where uvicorn is launched from
    import sys
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
        logger.info(f"   Added to sys.path: {backend_dir}")

    try:
        from tools.slackbot import start_slack_threads
    except ImportError as e:
        if "slackbot" in str(e):
            logger.error(f"❌ tools/slackbot.py not found — make sure it is in {backend_dir}/tools/")
        else:
            logger.warning(f"⚠️  Missing dependency — run: pip install slack-bolt httpx: {e}")
        return
    except Exception as e:
        logger.error(f"❌ tools/slackbot.py import failed: {e}")
        return

    try:
        start_slack_threads()
        logger.info("🤖 Slack bot started (poller + huddle + socket mode)")
    except Exception as e:
        logger.error(f"❌ Slack bot start_slack_threads() failed: {e}")

        logger.error(f"❌ Slack bot failed to start: {e}")


# ─────────────────────────────────────────────
# Lifespan (replaces on_event startup/shutdown)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"   Elasticsearch : {settings.ELASTIC_ENDPOINT}")

    mcp_url = os.getenv("ELASTIC_MCP_URL", "")
    if mcp_url:
        logger.info(f"   MCP Agent     : ENABLED ({mcp_url})")
    else:
        logger.warning("   MCP Agent     : DISABLED")

    # Start Slack bot in a daemon thread — dies cleanly when FastAPI stops
    slack_thread = threading.Thread(
        target=_start_slack_bot,
        daemon=True,
        name="slack-bot",
    )
    slack_thread.start()

    yield   # ← app runs here

    # ── Shutdown ─────────────────────────────
    logger.info(f"👋 Shutting down {settings.APP_NAME}")


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered lab report analysis via Elastic Agent Builder",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(llm_router)
app.include_router(scoring_router)


# ─────────────────────────────────────────────
# Root + Health
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
    }


@app.get("/health")
def health():
    try:
        from core.elasticsearch_client import get_es_client
        es    = get_es_client()
        count = es.count(settings.LAB_RESULTS_INDEX)
        es_status = "connected"
    except Exception:
        es_status = "disconnected"
        count     = 0

    slack_running = any(
        t.name == "slack-bot" and t.is_alive()
        for t in threading.enumerate()
    )

    return {
        "status":            "ok",
        "service":           settings.APP_NAME,
        "elasticsearch":     es_status,
        "lab_results_count": count,
        "mcp_enabled":       bool(os.getenv("ELASTIC_MCP_URL")),
        "slack_bot":         "running" if slack_running else "disabled",
    }


# ─────────────────────────────────────────────
# Elasticsearch Helper
# ─────────────────────────────────────────────

def get_es():
    return AsyncElasticsearch(
        os.getenv("ELASTIC_ENDPOINT"),
        api_key=os.getenv("ELASTIC_API_KEY"),
    )


# ─────────────────────────────────────────────
# Alert Models + Endpoints
# ─────────────────────────────────────────────

class AcknowledgeRequest(BaseModel):
    patient_id:      str
    acknowledged_by: str
    timestamp:       Optional[str] = None


class EscalateRequest(BaseModel):
    patient_id:   str
    escalated_by: str
    timestamp:    Optional[str] = None


@app.post("/api/alerts/acknowledge")
async def acknowledge_alert(req: AcknowledgeRequest):
    try:
        es = get_es()
        await es.index(
            index="labiq-alert-actions",
            document={
                "patient_id": req.patient_id,
                "action":     "acknowledged",
                "actor":      req.acknowledged_by,
                "timestamp":  req.timestamp or datetime.now(timezone.utc).isoformat(),
                "source":     "slack",
            }
        )
        await es.close()
        logger.info(f"✅ Alert acknowledged: {req.patient_id} by {req.acknowledged_by}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Acknowledge failed: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/api/alerts/escalate")
async def escalate_alert(req: EscalateRequest):
    try:
        es = get_es()
        await es.index(
            index="labiq-alert-actions",
            document={
                "patient_id": req.patient_id,
                "action":     "escalated",
                "actor":      req.escalated_by,
                "timestamp":  req.timestamp or datetime.now(timezone.utc).isoformat(),
                "source":     "slack",
            }
        )
        await es.close()
        logger.info(f"🔺 Alert escalated: {req.patient_id} by {req.escalated_by}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Escalate failed: {e}")
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Dev Runner
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # ← must be False when running Slack bot thread
        log_level=settings.LOG_LEVEL.lower(),
    )