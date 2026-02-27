# 🏥 LabIQ - Healthcare Lab Report Intelligence Agent

[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.11-005571?logo=elasticsearch)](https://www.elastic.co/)
[![ES|QL](https://img.shields.io/badge/ES%7CQL-Powered-00BFB3)](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql.html)
[![Agent Builder](https://img.shields.io/badge/Agent_Builder-MCP-FEC514)](https://www.elastic.co/agent-builder)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **AI-powered lab analysis that helps patients understand results and alerts doctors to critical values instantly.**

🏆 Built for the [Elasticsearch Agent Builder Hackathon 2026](https://elastic-agent-builder-hackathon.devpost.com/)

[📹 Demo Video](#-demo) • [🚀 Quick Start](#-quick-start) • [📚 Documentation](#-documentation) • [🏗️ Architecture](#%EF%B8%8F-architecture)

---

## 🎯 The Problem

**7 billion lab tests** performed annually in the US. Yet:

- 😰 Patients don't understand their results
- ⏰ Critical values sit unnoticed for hours/days
- 🕐 Doctors spend 5-10 min/patient explaining routine results
- 💸 **$187B/year** spent on preventable complications

**Real scenario:** Patient uploads lab results at 11 PM showing **triglycerides at 955 mg/dL** (pancreatitis risk). They wait until morning to hear from their doctor. ***This shouldn't happen.***

---

## 💡 The Solution

**LabIQ** is a multi-step AI agent powered by Elasticsearch Agent Builder that:

✅ Analyzes any lab report PDF in **<5 seconds**  
✅ Explains results in **plain language**  
✅ Detects **15+ clinical patterns** automatically  
✅ Tracks trends using **ES|QL time-series analytics**  
✅ Alerts doctors via **Slack in real-time**  
✅ Provides **evidence-based recommendations** with citations

**Not just search** - LabIQ orchestrates tools, reasons through complex medical data, and takes autonomous action.

---

## 🎬 Demo

[![LabIQ Demo](https://img.shields.io/badge/▶️_Watch_Demo-3_Minutes-FF0000?style=for-the-badge&logo=youtube)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)

**Demo highlights:**
- PDF upload → instant analysis
- Multi-step agent reasoning
- ES|QL trend detection
- Slack critical alert
- Kibana dashboard

---

## ⚡ Quick Start

### Prerequisites
```bash
# Required
- Python 3.10+
- Node.js 18+
- Elasticsearch 8.11+ (Serverless recommended)
- Kibana with Agent Builder enabled

# Optional (for Slack integration)
- Slack workspace with bot permissions
```

### 1. Clone Repository
```bash
git clone https://github.com/SIVAPRAKASH5668/LABIQ-Healthcare-Lab-Report-Intelligence-Agent.git
cd labiq
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials (see Configuration section)

# Run backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000`

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure API endpoint
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Run frontend
npm run dev
```

Frontend will be available at `http://localhost:3000`

### 4. Elasticsearch Setup
```bash
# Create indices
cd backend
python scripts/setup_elasticsearch.py

# Load sample data (optional)
python sample_data/generate_sample_pdfs.py
python scripts/upload_all_samples.py
```

### 5. Kibana Agent Builder Setup

1. Go to **Kibana → Management → Agent Builder**
2. Create new agent: **"LabIQ Medical Assistant"**
3. Add system prompt (see `docs/agent-prompt.md`)
4. Create 4 ES|QL tools (see `docs/kibana-tools.md`):
   - `get_patient_summary`
   - `find_abnormal_results`
   - `count_critical_flags`
   - `get_recent_test_dates`
5. Copy Agent ID and MCP URL to `.env`

---

## ⚙️ Configuration

### Backend `.env` File
```bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Elasticsearch Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ELASTIC_ENDPOINT=https://your-deployment.es.cloud:443
ELASTIC_API_KEY=your-base64-encoded-api-key
ELASTIC_CLOUD_ID=your-cloud-id  # Optional, if using Cloud

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Kibana Agent Builder (MCP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ELASTIC_MCP_URL=https://your-kibana.cloud/api/agent_builder/mcp
ELASTIC_AGENT_ID=labiq-medical-assistant

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Groq LLM (for advanced agent)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Slack Integration (Optional)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_ALERT_CHANNEL=#labiq-alerts
SLACK_ONCALL_USER_ID=U0XXXXXXXXX
ALERT_POLL_SECONDS=300
HUDDLE_HOUR=7
HUDDLE_TZ=America/New_York

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Application
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LABIQ_API_URL=http://localhost:8000
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Getting API Keys

#### Elasticsearch API Key
```bash
# In Kibana Dev Tools
POST /_security/api_key
{
  "name": "labiq-api-key",
  "role_descriptors": {
    "labiq_role": {
      "cluster": ["all"],
      "indices": [
        {
          "names": ["lab-results", "medical-knowledge"],
          "privileges": ["all"]
        }
      ]
    }
  }
}
```

#### Groq API Key
1. Go to https://console.groq.com
2. Sign up / Log in
3. Navigate to API Keys → Create New Key
4. Copy key starting with `gsk_`

#### Slack Tokens
1. Go to https://api.slack.com/apps
2. Create New App → From Scratch
3. **Bot Token:**
   - OAuth & Permissions → Bot Token Scopes:
     - `chat:write`, `commands`, `im:history`, `im:write`
   - Install to Workspace → Copy Bot User OAuth Token
4. **App Token:**
   - Basic Information → App-Level Tokens
   - Create token with `connections:write` scope
5. **Enable Socket Mode:**
   - Socket Mode → Enable
6. **Create Slash Command:**
   - Slash Commands → Create New Command
   - Command: `/labiq`
   - Request URL: (not needed for Socket Mode)

---

## 🏗️ Architecture
```
┌────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                         │
│  Web App (React)  │  Slack Bot  │  Kibana Agent UI        │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend                           │
│  • PDF Processing    • Chat (ES|QL + DSL)                 │
│  • Patient APIs      • LLM Agent (Groq + MCP)             │
│  • Analytics APIs    • Alert System                       │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│               Elasticsearch 8.11                           │
│  • ES|QL Analytics   • Ingest Pipeline (auto-status)      │
│  • kNN Similarity    • Function Score Ranking             │
│  • Hybrid Search     • Time-Series Aggregations           │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                   Data Layer                               │
│  lab-results index  │  medical-knowledge  │  vectors       │
└────────────────────────────────────────────────────────────┘
```

**Key Innovations:**
- 🔄 **Hybrid ES|QL + DSL** - ES|QL for aggregations, DSL for nested access
- ⚡ **Ingest Pipeline** - Painless script auto-detects status and risk scores
- 🧠 **Clinical Pattern Detection** - 15+ medical syndromes identified automatically
- 🤖 **Multi-Step Agent** - Orchestrates tools across 3+ reasoning steps
- 📊 **Time-Series Analytics** - ES|QL tracks biomarker trends over months/years

---

## 📁 Project Structure
```
labiq/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── api/
│   │   ├── alerts.py              # Real-time alert detection
│   │   ├── chat.py                # Keyword-based chat with ES|QL
│   │   ├── esql.py                # ES|QL query executor
│   │   ├── llm.py                 # Groq + MCP advanced agent
│   │   ├── patients.py            # Patient data endpoints
│   │   ├── analytics.py           # kNN, percentile, scoring
│   │   └── upload.py              # PDF upload handler
│   ├── core/
│   │   ├── config.py              # Configuration & reference ranges
│   │   └── elasticsearch_client.py # ES client wrapper
│   ├── tools/
│   │   ├── pdf_processor.py       # Dynamic PDF extraction
│   │   ├── lab_analyzer.py        # Trend analysis & summaries
│   │   ├── knowledge_search.py    # Medical knowledge base search
│   │   └── slack_bot.py           # Proactive Slack integration
│   ├── sample_data/
│   │   └── generate_sample_pdfs.py # Create test data
│   ├── scripts/
│   │   ├── setup_elasticsearch.py  # Create indices & pipeline
│   │   └── upload_all_samples.py   # Bulk data loader
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Main application
│   │   ├── layout.tsx             # Root layout
│   │   └── globals.css            # Tailwind styles
│   ├── components/
│   │   ├── UploadTab.tsx          # PDF upload interface
│   │   ├── ChatTab.tsx            # Chat interface
│   │   ├── DashboardTab.tsx       # Analytics display
│   │   ├── RiskGauge.tsx          # Risk score visualization
│   │   ├── AlertFeed.tsx          # Live alert stream
│   │   └── BiomarkerCharts.tsx    # Sparkline trends
│   ├── package.json
│   └── next.config.js
│
├── docs/
│   ├── ARCHITECTURE.md            # Detailed architecture
│   ├── API.md                     # API documentation
│   ├── KIBANA_SETUP.md            # Agent Builder guide
│   ├── agent-prompt.md            # System prompt for agent
│   └── kibana-tools.md            # ES|QL tool definitions
│
├── README.md                      # This file
├── LICENSE                        # MIT License
└── .gitignore
```

---

## 🔧 API Endpoints

### Upload & Processing
```http
POST /api/upload-lab-report
Content-Type: multipart/form-data

file: lab_report.pdf
patient_id: PAT001
```

### Patient Data
```http
GET  /api/patients                      # List all patients
GET  /api/patients/{id}/summary         # Patient overview
GET  /api/patients/{id}/biomarkers      # Time-series biomarker data
GET  /api/patients/{id}/risk-trend      # Risk progression over time
GET  /api/patients/{id}/risk-score      # Cardiovascular risk (0-100)
```

### Analytics
```http
GET  /api/patients/{id}/similar         # kNN similar patients
GET  /api/patients/{id}/percentile      # Risk percentile ranking
GET  /api/patients/{id}/scored-panels   # Function score ranked results
GET  /api/analytics/population          # Population-level statistics
```

### Chat & AI
```http
POST /api/chat                          # Simple keyword-based chat
POST /api/llm/chat                      # Advanced LLM agent

{
  "message": "Analyze my glucose trends",
  "patient_id": "PAT001",
  "conversation_history": []
}
```

### Utilities
```http
GET  /health                            # System health check
GET  /api/mcp/discover                  # List available MCP tools
POST /api/esql/run                      # Execute custom ES|QL query
GET  /api/alerts/feed?patient_id=PAT001 # Real-time alert feed
```

---

## 🧪 Testing

### Run Backend Tests
```bash
cd backend
pytest tests/ -v --cov=. --cov-report=html
```

### Test ES|QL Queries
```bash
# Test patient summary
curl -X POST http://localhost:8000/api/esql/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "FROM lab-results | WHERE patient_id == \"PAT001\" | STATS total = COUNT(*)"
  }'
```

### Test Chat Agent
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show my lab summary",
    "patient_id": "PAT001"
  }'
```

### Test LLM Agent
```bash
curl -X POST http://localhost:8000/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Should I be worried about my latest results?",
    "patient_id": "PAT001"
  }'
```

---

## 🎨 ES|QL Examples

### Patient Summary
```sql
FROM lab-results
| WHERE patient_id == "PAT001"
| STATS 
    total_panels = COUNT(*),
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical = COUNT(*) WHERE critical_flags IS NOT NULL,
    avg_risk = AVG(document_risk_score)
```

### Glucose Trend Analysis
```sql
FROM lab-results
| WHERE patient_id == "PAT001"
| MV_EXPAND results
| WHERE results.test_name == "Glucose"
| STATS 
    latest = MAX(results.value),
    earliest = MIN(results.value),
    avg = AVG(results.value)
| EVAL
    pct_change = ROUND((latest - earliest) / earliest * 100, 1),
    trend = CASE(
        latest > avg * 1.1, "increasing",
        latest < avg * 0.9, "decreasing",
        "stable"
    )
```

### Risk Ranking Across All Patients
```sql
FROM lab-results
| STATS
    total_panels = COUNT(*),
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical = COUNT(*) WHERE critical_flags IS NOT NULL,
    max_risk = MAX(document_risk_score)
  BY patient_id
| EVAL composite_risk = critical * 3 + abnormal
| SORT composite_risk DESC
| LIMIT 10
```

---

## 🤖 Slack Bot Commands

### Slash Commands
```
/labiq summary PAT001           # Patient overview
/labiq critical values PAT002   # Urgent findings
/labiq risk assessment PAT001   # Cardiovascular risk
/labiq compare all patients     # Triage ranking
/labiq huddle                   # Morning triage summary
```

### Mentions
```
@LabIQ analyze trends for PAT001
@LabIQ what does high cholesterol mean?
@LabIQ show me patients needing attention
```

### Proactive Features
- 🚨 **Critical alerts** - Posted to `#labiq-alerts` within 5 minutes
- 📅 **Daily huddle** - 7am triage summary of all patients
- 🔘 **Interactive buttons** - Acknowledge / Escalate / Snooze / Ask AI
- 📞 **Escalation chain** - Auto-notify on-call physician

---

## 🎓 Clinical Pattern Detection

LabIQ automatically detects **15+ medical patterns**:

✅ **Metabolic Syndrome** (High TG + Low HDL + High Glucose)  
✅ **Prediabetes** (HbA1c 5.7-6.4% or Glucose 100-125)  
✅ **Diabetes** (HbA1c ≥6.5% or Glucose ≥126)  
✅ **Kidney Disease Stages** (eGFR <60)  
✅ **Liver Damage** (AST/ALT ratio >2)  
✅ **Anemia** (Hemoglobin <12 g/dL)  
✅ **Thyroid Dysfunction** (TSH >10 or <0.4)  
✅ **Cardiovascular Risk** (TC/HDL ratio >5)  
✅ **Pancreatitis Risk** (Triglycerides >500)  
✅ **Iron Deficiency** (Ferritin <15)  
✅ **Vitamin D Deficiency** (<20 ng/mL)  
✅ **Electrolyte Imbalance** (K >5.5 or <3.0)  
✅ **Lipid Abnormalities** (LDL >130, HDL <40)  
✅ **Inflammation** (CRP >3 mg/L)  
✅ **Vitamin B12 Deficiency** (<300 pg/mL)

**Example output:**
```
METABOLIC SYNDROME (3/3): TG 955, HDL 32, Glu 118 — CVD+diabetes risk
TG 955 mg/dL — CRITICAL pancreatitis risk (nl<150)
TC/HDL ratio 6.9 — >5 = high cardiovascular risk
HbA1c 6.2% — PRE-DIABETES (5.7–6.4%)
```

---

## 🚢 Deployment

### Docker Compose (Recommended)
```bash
# Clone repo
git clone https://github.com/yourusername/labiq.git
cd labiq

# Configure .env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Edit with your credentials

# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f backend
```

**Services:**
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Elasticsearch: http://localhost:9200 (if running locally)

### Production Deployment

**Backend (FastAPI)**
```bash
# Using Gunicorn + Uvicorn workers
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --log-level info
```

**Frontend (Next.js)**
```bash
# Build static export
npm run build
npm run start

# Or deploy to Vercel/Netlify
vercel deploy --prod
```

**Elasticsearch**
- Use [Elastic Cloud](https://cloud.elastic.co/) (Serverless recommended)
- Or self-host with proper security (TLS, authentication)

---

## 🔒 Security Considerations

### HIPAA Compliance Notes

⚠️ **This is a hackathon prototype.** For production healthcare use, implement:

- ✅ **Encryption at rest** - Enable on Elasticsearch indices
- ✅ **Encryption in transit** - Use TLS for all connections
- ✅ **Access controls** - Role-based authentication (RBAC)
- ✅ **Audit logging** - Track all data access
- ✅ **PHI handling** - Follow HIPAA guidelines for patient data
- ✅ **Data retention** - Implement lifecycle policies
- ✅ **Backup & disaster recovery** - Automated backups
- ✅ **Business Associate Agreement** - With Elastic, Groq, Slack

### Current Security Features

✅ API key authentication for Elasticsearch  
✅ Environment variables for secrets  
✅ No PHI in application logs  
✅ CORS configuration for frontend  
✅ Request validation with Pydantic  
✅ Rate limiting (configurable)  

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run linters
black backend/
isort backend/
flake8 backend/
mypy backend/

# Run tests
pytest tests/ -v
```

### Reporting Issues

Found a bug? Have a feature request?

1. Check [existing issues](https://github.com/yourusername/labiq/issues)
2. Create new issue with template
3. Provide details: OS, Python version, error logs

---

## 📈 Roadmap

### ✅ Phase 1 (Current - Hackathon MVP)
- [x] PDF processing with dynamic extraction
- [x] ES|QL time-series analytics
- [x] Multi-step agent with MCP
- [x] Slack integration with proactive alerts
- [x] Clinical pattern detection (15+ patterns)
- [x] Risk scoring algorithm
- [x] Kibana dashboards

### 🔄 Phase 2 (Q2 2026)
- [ ] FHIR integration (EHR connectivity)
- [ ] Multi-language support (Spanish, Hindi, Chinese)
- [ ] Medication interaction warnings
- [ ] Mobile app (iOS + Android)
- [ ] Voice interface (Alexa/Google Home)

### 🚀 Phase 3 (Q3-Q4 2026)
- [ ] Predictive analytics (ML models for risk prediction)
- [ ] Treatment effectiveness tracking
- [ ] Population health dashboards
- [ ] Clinical trial matching
- [ ] Telemedicine integration
- [ ] Insurance pre-authorization automation

### 🌙 Future Ideas
- [ ] Genomic risk scoring
- [ ] Wearable device integration (CGM, fitness trackers)
- [ ] AI doctor co-pilot (real-time EHR assistance)
- [ ] Research data contribution (de-identified datasets)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
```
Copyright (c) 2026 LabIQ Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

**Built with:**
- [Elasticsearch](https://www.elastic.co/) - Search & analytics engine
- [ES|QL](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql.html) - Piped query language
- [Kibana Agent Builder](https://www.elastic.co/agent-builder) - Multi-step agent framework
- [Groq](https://groq.com/) - Fast LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) + [Next.js](https://nextjs.org/) - Frontend framework
- [Slack Bolt](https://slack.dev/bolt-python/) - Slack integration SDK

**Medical guidelines from:**
- American Diabetes Association (ADA)
- American Heart Association (AHA)
- National Kidney Foundation (NKF)
- Mayo Clinic Reference Values

**Special thanks to:**
- Elastic team for Agent Builder and ES|QL innovations
- Hackathon participants for feedback and collaboration
- Healthcare professionals who validated clinical logic

---

## 📞 Contact & Support

- **GitHub Issues:** [Report bugs](https://github.com/yourusername/labiq/issues)
- **Discussions:** [Ask questions](https://github.com/yourusername/labiq/discussions)
- **Email:** labiq-support@example.com
- **Twitter:** [@LabIQ_Health](https://twitter.com/LabIQ_Health)
- **Hackathon:** [Devpost Project](https://devpost.com/software/labiq)

---

<div align="center">

**LabIQ - Because understanding your health shouldn't require a medical degree.** 🏥🤖

Made with ❤️ for the Elasticsearch Agent Builder Hackathon 2026

[![Star on GitHub](https://img.shields.io/github/stars/yourusername/labiq?style=social)](https://github.com/yourusername/labiq)
[![Fork on GitHub](https://img.shields.io/github/forks/yourusername/labiq?style=social)](https://github.com/yourusername/labiq/fork)

[⬆ Back to Top](#-labiq---healthcare-lab-report-intelligence-agent)

</div>
