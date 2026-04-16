# Job Hunter Agent 🤖

A **multi-agent AI system** that automates job searching, resume tailoring, and interview preparation — built with CrewAI, RAG, and Pydantic.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Vanilla JS)                  │
│  Search Form → Progress View → Job Cards (expandable)   │
│           → Prep Modal with Agent Status                 │
└────────────────────┬────────────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────────────┐
│                Flask Backend (server.py)                  │
├─────────────────────────────────────────────────────────┤
│  Fast Scanner (Zero-Token)        │  CrewAI Prep Suite  │
│  ├── Greenhouse API               │  ├── Resume Tailor  │
│  ├── Ashby API                     │  ├── Researcher     │
│  ├── Lever API                     │  └── Interview Coach│
│  └── DuckDuckGo Search            │                     │
├─────────────────────────────────────────────────────────┤
│  RAG Pipeline              │  Structured Output          │
│  ├── Resume Chunker        │  ├── Pydantic Schemas       │
│  ├── Sentence-Transformers │  └── JD Field Extraction    │
│  └── ChromaDB (Vector DB)  │                             │
├─────────────────────────────────────────────────────────┤
│  SQLite DB  │  PDF Generator (Playwright)  │  Cache      │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Zero-Token Fast Scan
Queries 15+ company career pages (Greenhouse, Ashby, Lever APIs) and DuckDuckGo simultaneously with zero LLM tokens. Extracts structured JD fields (salary, experience, skills) directly from API responses.

### 2. CrewAI Multi-Agent System
Three specialized AI agents collaborate sequentially:
- **Resume Tailor Agent** — Rewrites your resume to match the target JD
- **Company Researcher Agent** — Gathers intelligence about the company via web search
- **Interview Coach Agent** — Creates a personalized interview prep guide

### 3. RAG Pipeline (ChromaDB + Sentence-Transformers)
Your resume is chunked into semantic sections (experience, skills, education, projects) and embedded into ChromaDB using `all-MiniLM-L6-v2`. When you click "Prep Me", the most relevant resume sections are retrieved based on JD similarity.

### 4. Structured Job Descriptions
Each job card displays:
- 💰 Salary range (extracted from ATS data)
- 📊 Experience level (inferred from title + description)
- 🏷️ Skills (auto-detected from known tech stack)
- 📋 Expandable JD with description, requirements, responsibilities

### 5. PDF Generation
ATS-compatible PDFs generated via Playwright headless Chromium with professional styling.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS, CSS (Glassmorphism, dark mode) |
| Backend | Python, Flask, Flask-CORS |
| AI Agents | CrewAI, Groq (Llama 3.3 70B) |
| RAG | ChromaDB, Sentence-Transformers |
| Scraping | Requests, DuckDuckGo Search |
| Database | SQLite |
| PDF | Playwright, Markdown |
| Validation | Pydantic |

## Requirements
- Python 3.10+
- Groq API key (free at console.groq.com)
- ~500MB disk for sentence-transformers model (downloaded on first run)

## Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd job-hunter-agent
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Install Playwright browser
playwright install chromium

# 3. Configure API keys
copy .env.example .env
# Edit .env with your Groq API key(s)

# 4. Run
python run.py
# Open http://localhost:5000
```

## Project Structure

```
job-hunter-agent/
├── backend/
│   ├── agents/
│   │   ├── crew.py              # CrewAI multi-agent orchestrator
│   │   ├── schemas.py           # Pydantic output schemas
│   │   ├── resume_writer.py     # Fallback resume agent
│   │   ├── researcher.py        # Fallback research agent
│   │   ├── interview_prep.py    # Fallback interview agent
│   │   └── pdf_generator.py     # Markdown → PDF via Playwright
│   ├── pipeline/
│   │   ├── orchestrator.py      # Pipeline coordinator
│   │   ├── fast_scanner.py      # Zero-token ATS scanner
│   │   └── rate_limiter.py      # Groq key rotation + backoff
│   ├── resume/
│   │   ├── parser.py            # PDF/DOCX text extraction
│   │   └── rag.py               # RAG: chunking + ChromaDB embedding
│   ├── storage/
│   │   ├── db.py                # SQLite schema + migrations
│   │   └── cache.py             # TTL-based result cache
│   ├── utils/
│   │   └── logger.py            # Structured logging
│   ├── config.py                # Central configuration
│   └── server.py                # Flask API server
├── frontend/
│   ├── css/style.css            # Premium dark UI
│   ├── js/
│   │   ├── app.js               # Main controller
│   │   ├── results.js           # Job card renderer
│   │   ├── poller.js            # Long-polling client
│   │   └── upload.js            # Drag-drop file upload
│   └── index.html               # Single-page app
├── config/portals.yml           # Tracked company APIs
├── requirements.txt
├── run.py
└── README.md
```