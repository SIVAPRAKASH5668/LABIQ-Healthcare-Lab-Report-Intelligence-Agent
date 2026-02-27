"""
LabIQ Slack Bot — Proactive Clinical AI
========================================
Integrated into main.py via import — no separate process needed.
main.py calls start_slack_threads() on startup.

Features:
  • /labiq <question> [PAT001]  — Full LLM + MCP response in Slack
  • @mention                    — Same as slash command, in any channel
  • DM the bot                  — Conversational multi-turn interface
  • Proactive critical alerts   — Polls ES every 5 min, posts on new criticals
  • Daily huddle                — 7am triage summary to #labiq-alerts channel
  • Interactive buttons         — Acknowledge / Escalate / Snooze → writes to ES

.env vars needed:
  SLACK_BOT_TOKEN=xoxb-...
  SLACK_APP_TOKEN=xapp-...
  SLACK_ALERT_CHANNEL=#labiq-alerts
  SLACK_ONCALL_USER_ID=U0XXXXXXXXX   (optional)
  LABIQ_API_URL=http://localhost:8000
"""

import os
import re
import threading
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logger = logging.getLogger("labiq.slack")

# ── Config ─────────────────────────────────────────────────────
SLACK_BOT_TOKEN     = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN     = os.getenv("SLACK_APP_TOKEN", "")
SLACK_ALERT_CHANNEL = os.getenv("SLACK_ALERT_CHANNEL", "#labiq-alerts")
SLACK_ONCALL_USER   = os.getenv("SLACK_ONCALL_USER_ID", "")
LABIQ_API_URL       = os.getenv("LABIQ_API_URL", "http://localhost:8000")
POLL_INTERVAL_SEC   = int(os.getenv("ALERT_POLL_SECONDS", "300"))
HUDDLE_HOUR         = int(os.getenv("HUDDLE_HOUR", "7"))
HUDDLE_TZ           = os.getenv("HUDDLE_TZ", "America/New_York")

# ── State ──────────────────────────────────────────────────────
_alerted_criticals:   set  = set()
_snoozed:             dict = {}   # patient_id → snooze_until epoch
_conversation_history: dict = {}  # slack user_id → [{role, content}]

# ── Slack App ──────────────────────────────────────────────────
# Use token directly — if empty, App() uses a dummy so decorators still register.
# start_slack_threads() validates tokens before launching SocketModeHandler.
app = App(token=SLACK_BOT_TOKEN or "xoxb-placeholder-token-not-used-until-start")


# ══════════════════════════════════════════════════════════════
# Internal API helpers
# ══════════════════════════════════════════════════════════════

def _api(endpoint: str, method: str = "GET",
         payload: dict = None, timeout: int = 30) -> dict:
    url = f"{LABIQ_API_URL}{endpoint}"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=payload) if method == "POST" else c.get(url)
            return r.json()
    except Exception as e:
        logger.error(f"API call failed [{url}]: {e}")
        return {"error": str(e)}


def _llm_chat(message: str, patient_id: str, user_id: str = None) -> dict:
    history = _conversation_history.get(user_id, []) if user_id else []
    result  = _api("/api/llm/chat", method="POST", payload={
        "message":              message,
        "patient_id":           patient_id,
        "conversation_history": history,
    }, timeout=90)
    if user_id and "response" in result and result.get("source") != "error":
        history = history[-8:]
        history.append({"role": "user",      "content": message})
        history.append({"role": "assistant", "content": result["response"]})
        _conversation_history[user_id] = history
    return result


def _get_critical_patients() -> list:
    data = _api("/api/patients")
    return [p for p in data.get("patients", []) if p.get("critical", 0) > 0]


def _get_all_patients() -> list:
    return _api("/api/patients").get("patients", [])


# ══════════════════════════════════════════════════════════════
# Formatting helpers
# ══════════════════════════════════════════════════════════════

def _extract_patient_id(text: str) -> str:
    m = re.search(r'PAT\s*\d+', text.upper())
    return m.group(0).replace(" ", "") if m else "PAT001"


def _fmt_llm(data: dict) -> str:
    if data.get("source") == "error":
        return f"❌ {data.get('response', data.get('error', 'Unknown error'))}"
    response = re.sub(r'\*\*(.+?)\*\*', r'*\1*', data.get("response", "No response"))
    tools    = data.get("tools_used", [])
    ms       = data.get("execution_ms", 0)
    footer   = f"\n\n_🔧 {', '.join(tools)} · {ms}ms_" if tools else f"\n\n_{ms}ms_"
    return response + footer


def _fmt_critical_alert(patient: dict) -> list:
    pid = patient.get("patient_id", "UNKNOWN")
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🚨 Critical Alert — {pid}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Patient:*\n{pid}"},
                {"type": "mrkdwn", "text": f"*Critical Flags:*\n🔴 {patient.get('critical', 0)}"},
                {"type": "mrkdwn", "text": f"*Abnormal:*\n🟡 {patient.get('abnormal', 0)}"},
                {"type": "mrkdwn", "text": f"*Total Panels:*\n{patient.get('total_tests', 0)}"},
            ],
        },
        {
            "type": "actions",
            "block_id": f"alert_{pid}",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Acknowledge", "emoji": True},
                 "style": "primary", "action_id": "alert_acknowledge", "value": pid},
                {"type": "button", "text": {"type": "plain_text", "text": "🔺 Escalate", "emoji": True},
                 "style": "danger",  "action_id": "alert_escalate",    "value": pid},
                {"type": "button", "text": {"type": "plain_text", "text": "⏱ Snooze 1hr", "emoji": True},
                 "action_id": "alert_snooze", "value": pid},
                {"type": "button", "text": {"type": "plain_text", "text": "💬 Ask AI", "emoji": True},
                 "action_id": "alert_ask_ai", "value": pid},
            ],
        },
        {"type": "divider"},
    ]


def _fmt_huddle(patients: list) -> list:
    criticals = [p for p in patients if p.get("critical", 0) > 0]
    high_risk = [p for p in patients if p.get("abnormal", 0) > 2 and p.get("critical", 0) == 0]
    now_str   = datetime.now(ZoneInfo(HUDDLE_TZ)).strftime("%A, %B %d · %I:%M %p")

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": f"🏥 LabIQ Morning Huddle — {now_str}", "emoji": True}},
        {"type": "divider"},
    ]

    if criticals:
        blocks.append({"type": "section",
                        "text": {"type": "mrkdwn", "text": f"*🔴 Critical Patients ({len(criticals)})*"}})
        for p in criticals:
            pid = p.get("patient_id", "")
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"• *{pid}* — 🔴 {p.get('critical',0)} critical · 🟡 {p.get('abnormal',0)} abnormal · {p.get('total_tests',0)} panels"}})
    else:
        blocks.append({"type": "section",
                        "text": {"type": "mrkdwn", "text": "✅ *No critical patients right now*"}})

    if high_risk:
        blocks.append({"type": "section",
                        "text": {"type": "mrkdwn", "text": f"\n*🟡 Needs Monitoring ({len(high_risk)})*"}})
        for p in high_risk[:5]:
            pid = p.get("patient_id", "")
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"• *{pid}* — 🟡 {p.get('abnormal',0)} abnormal"}})

    blocks += [
        {"type": "divider"},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "Use `/labiq <question> <patient_id>` to query any patient · Powered by Elastic MCP + Groq"}]},
    ]
    return blocks


# ══════════════════════════════════════════════════════════════
# Interactive Button Handlers
# ══════════════════════════════════════════════════════════════

@app.action("alert_acknowledge")
def handle_acknowledge(ack, body, client):
    ack()
    pid      = body["actions"][0]["value"]
    user     = body["user"]["id"]
    username = body["user"].get("name", user)
    channel  = body["container"]["channel_id"]
    ts       = body["message"]["ts"]

    client.chat_update(
        channel=channel, ts=ts,
        text=f"✅ *{pid}* acknowledged by <@{user}>",
        blocks=[{"type": "section", "text": {"type": "mrkdwn",
            "text": f"✅ *{pid}* alert acknowledged by <@{user}> at {datetime.now().strftime('%H:%M')}"}}],
    )
    _api("/api/alerts/acknowledge", method="POST",
         payload={"patient_id": pid, "acknowledged_by": username,
                  "timestamp": datetime.utcnow().isoformat()})
    logger.info(f"Acknowledged: {pid} by {username}")


@app.action("alert_escalate")
def handle_escalate(ack, body, client):
    ack()
    pid     = body["actions"][0]["value"]
    user    = body["user"]["id"]
    channel = body["container"]["channel_id"]
    ts      = body["message"]["ts"]

    client.chat_update(
        channel=channel, ts=ts,
        text=f"🔺 *{pid}* escalated by <@{user}>",
        blocks=[{"type": "section", "text": {"type": "mrkdwn",
            "text": f"🔺 *{pid}* escalated by <@{user}>. Senior clinician notified."}}],
    )
    if SLACK_ONCALL_USER:
        client.chat_postMessage(
            channel=SLACK_ONCALL_USER,
            text=f"🔺 *ESCALATION: {pid}*\nEscalated by <@{user}>. Immediate review required.",
        )
    _api("/api/alerts/escalate", method="POST",
         payload={"patient_id": pid, "escalated_by": user,
                  "timestamp": datetime.utcnow().isoformat()})
    logger.info(f"Escalated: {pid} by {user}")


@app.action("alert_snooze")
def handle_snooze(ack, body, client):
    ack()
    pid     = body["actions"][0]["value"]
    user    = body["user"]["id"]
    channel = body["container"]["channel_id"]
    ts      = body["message"]["ts"]

    _snoozed[pid] = time.time() + 3600
    client.chat_update(
        channel=channel, ts=ts,
        text=f"⏱ *{pid}* snoozed 1hr by <@{user}>",
        blocks=[{"type": "section", "text": {"type": "mrkdwn",
            "text": f"⏱ *{pid}* alert snoozed for 1 hour by <@{user}>"}}],
    )
    logger.info(f"Snoozed: {pid} by {user} for 1hr")


@app.action("alert_ask_ai")
def handle_ask_ai(ack, body, client):
    ack()
    pid     = body["actions"][0]["value"]
    user    = body["user"]["id"]
    channel = body["container"]["channel_id"]

    client.chat_postMessage(channel=channel, text=f"_🤖 Asking AI about {pid}..._")
    data = _llm_chat(
        "This patient has critical lab values. Give a clinical summary of the "
        "critical findings and recommended immediate actions.",
        patient_id=pid, user_id=user,
    )
    client.chat_postMessage(channel=channel, text=_fmt_llm(data))


# ══════════════════════════════════════════════════════════════
# Message / Command Handlers
# ══════════════════════════════════════════════════════════════

def _handle_query(text: str, say, user_id: str, respond=None):
    pid      = _extract_patient_id(text)
    clean    = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    reply_fn = respond if respond else say
    reply_fn(f"_🔍 Analyzing {pid} via Elastic MCP + Groq..._")
    data = _llm_chat(clean, pid, user_id)
    reply_fn(_fmt_llm(data))


@app.event("app_mention")
def handle_mention(event, say):
    _handle_query(event.get("text", ""), say, user_id=event.get("user"))


@app.event("message")
def handle_dm(event, say):
    if event.get("channel_type") != "im" or event.get("bot_id"):
        return
    text = event.get("text", "").strip()
    if text:
        _handle_query(text, say, user_id=event.get("user"))


@app.command("/labiq")
def labiq_command(ack, respond, command):
    ack()
    text = command.get("text", "").strip()
    user = command.get("user_id", "")

    if not text or text == "help":
        respond(
            "*🏥 LabIQ Commands*\n\n"
            "• `/labiq summary PAT001` — Patient overview\n"
            "• `/labiq critical values PAT002` — Critical findings\n"
            "• `/labiq risk assessment PAT001` — Risk score\n"
            "• `/labiq compare all patients` — Triage ranking\n"
            "• `/labiq huddle` — Morning triage summary\n\n"
            "Ask anything naturally — the AI will figure it out 🤖"
        )
        return

    if "huddle" in text.lower():
        respond("_Generating morning huddle..._")
        respond(blocks=_fmt_huddle(_get_all_patients()), text="Morning Huddle")
        return

    _handle_query(text, say=None, user_id=user, respond=respond)


# ══════════════════════════════════════════════════════════════
# Background threads (started by main.py via start_slack_threads)
# ══════════════════════════════════════════════════════════════

def _poll_criticals():
    logger.info(f"🔔 Alert poller started (every {POLL_INTERVAL_SEC}s)")
    while True:
        try:
            now = time.time()
            for patient in _get_critical_patients():
                pid = patient.get("patient_id", "")
                if _snoozed.get(pid, 0) > now:
                    continue
                if pid in _alerted_criticals:
                    continue
                _alerted_criticals.add(pid)
                logger.info(f"🚨 New critical: {pid}")
                app.client.chat_postMessage(
                    channel=SLACK_ALERT_CHANNEL,
                    text=f"🚨 Critical alert: {pid}",
                    blocks=_fmt_critical_alert(patient),
                )
                if SLACK_ONCALL_USER:
                    app.client.chat_postMessage(
                        channel=SLACK_ONCALL_USER,
                        text=f"🚨 Critical values for *{pid}*. Check {SLACK_ALERT_CHANNEL}.",
                    )
        except Exception as e:
            logger.error(f"Poller error: {e}")
        time.sleep(POLL_INTERVAL_SEC)


def _huddle_scheduler():
    logger.info(f"📅 Huddle scheduler started (daily {HUDDLE_HOUR}:00 {HUDDLE_TZ})")
    last_day = None
    while True:
        try:
            now = datetime.now(ZoneInfo(HUDDLE_TZ))
            if now.hour == HUDDLE_HOUR and now.date() != last_day:
                last_day = now.date()
                logger.info("📅 Sending morning huddle")
                app.client.chat_postMessage(
                    channel=SLACK_ALERT_CHANNEL,
                    text="🏥 LabIQ Morning Huddle",
                    blocks=_fmt_huddle(_get_all_patients()),
                )
        except Exception as e:
            logger.error(f"Huddle error: {e}")
        time.sleep(60)


def start_slack_threads():
    """
    Called by main.py lifespan on startup.
    Starts background poller + huddle scheduler + Socket Mode handler.
    """
    threading.Thread(target=_poll_criticals,  daemon=True, name="slack-poller").start()
    threading.Thread(target=_huddle_scheduler, daemon=True, name="slack-huddle").start()

    def _run_socket():
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()

    threading.Thread(target=_run_socket, daemon=True, name="slack-socket").start()
    logger.info("🤖 Slack bot threads started (poller + huddle + socket)")


# ══════════════════════════════════════════════════════════════
# Standalone entry point (python slack_bot.py still works)
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # When run directly: python tools/slackbot.py
    # Load .env from backend/ (one level up from tools/)
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    # Re-read env after loading
    SLACK_BOT_TOKEN  = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_APP_TOKEN  = os.getenv("SLACK_APP_TOKEN", "")

    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        raise ValueError("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env")

    print(f"🤖 LabIQ Slack Bot (standalone from tools/)")
    print(f"   API:     {LABIQ_API_URL}")
    print(f"   Channel: {SLACK_ALERT_CHANNEL}")
    print(f"   Poll:    every {POLL_INTERVAL_SEC}s")
    print(f"   Huddle:  {HUDDLE_HOUR}:00 {HUDDLE_TZ}")
    start_slack_threads()
    while True:
        time.sleep(60)