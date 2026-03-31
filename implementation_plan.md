# 🎯 Job Hunter Agent — Full Polish Implementation Plan

## Architecture Overview

```mermaid
graph TD
    A[Frontend - HTML/CSS/JS] -->|REST API + SSE| B[Flask Backend]
    B --> C[Job Scraper Engine]
    B --> D[CrewAI Agent Pipeline]
    B --> E[Resume Parser]
    C -->|DuckDuckGo + Portal Scrapers| F[Job Portals]
    D -->|Groq API with Retry| G[LLM]
    E -->|PyPDF2 / python-docx| H[Resume Files]
    B --> I[SQLite / JSON Storage]
```

## Phase 1: Backend API (Flask)
Replace Streamlit with a proper Flask API server.

## Phase 2: Premium Frontend (HTML/CSS/JS)
Dark theme with glassmorphism, drag-and-drop resume upload, date picker, portal selector.

## Phase 3: Enhanced Scraping
15-20 jobs from 7+ portals via DuckDuckGo proxy searches.

## Phase 4: Resume Upload
PDF and DOCX support.

## Phase 5: Smart Rate Limit Handling
Exponential backoff + batch processing + key rotation.

## Phase 6: Additional Features
Persistent storage, search history, export.

See full details in the artifacts folder.
