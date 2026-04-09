# Job Hunter Agent

A 5-stage AI pipeline that automates job searching, matching, and interview preparation.

## Features
1. **Search & Scrape**: Automatically discovers jobs across multiple portals with DuckDuckGo and Bing fallback.
2. **Robust Extraction**: Fetches job descriptions overcoming React SPAs via Playwright, then structures into JSON via LLM.
3. **AI Matching**: Scores your resume against found jobs to help you focus on the best opportunities.
4. **Tailored Resume Generator**: Reconstructs your resume to highlight the skills relevant to the specific job you select.
5. **Interview Prep**: Researches the company and prepares a bespoke strategy guide with custom questions and answers.

## Requirements
- Python 3.10+
- Free Groq Accounts (for rotating API keys and rate-limit bypassing)
- (Optional) Bing Web Search API key for expanded fallback search capacity

## Setup instructions
1. Clone the repository.
2. Create your virtual environment and run `pip install -r requirements.txt`.
3. Install playwright browsers: `playwright install chromium`.
4. Create `.env` from `.env.example` and add your keys.
5. Start server: `python backend/server.py`.

## Architecture Note
This version of Job Hunter Agent drops high-overhead UI frameworks and uses a robust Python backend (Flask API + SQLite) with an ultra-light Vanilla JS foreground utilizing long-polling rather than stateful SSEs.
