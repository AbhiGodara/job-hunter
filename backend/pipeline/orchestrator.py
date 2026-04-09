"""
Runs the full 5-stage pipeline in a background thread.
Writes status updates to SQLite so frontend can poll.
"""
import uuid, threading, logging, json
from backend.storage.db import get_conn
from backend.scraper.search_engine import search_all_portals
from backend.scraper.content_fetcher import fetch_job_content
from backend.agents.extractor import extract_job
from backend.agents.matcher import match_job
from backend.resume.parser import parse_resume

log = logging.getLogger(__name__)

def create_run(role: str, location: str) -> str:
    run_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute("INSERT INTO job_runs (id, role, location, status) VALUES (?,?,?,'pending')",
                     (run_id, role, location))
    return run_id

def update_run(run_id: str, **kwargs):
    """Update any field on a job_run row."""
    fields = ", ".join(f"{k}=?" for k in kwargs)
    with get_conn() as conn:
        conn.execute(f"UPDATE job_runs SET {fields} WHERE id=?",
                     (*kwargs.values(), run_id))

def get_run_status(run_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM job_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return {"error": "run not found"}
        jobs = conn.execute(
            "SELECT id, title, company, location, salary, portal, url, "
            "match_score, match_reason FROM jobs WHERE run_id=? ORDER BY match_score DESC",
            (run_id,)
        ).fetchall()
        return {
            "run_id":   run_id,
            "status":   row["status"],
            "stage":    row["stage"],
            "progress": row["progress"],
            "jobs":     [dict(j) for j in jobs]
        }

def run_pipeline(run_id: str, role: str, location: str, resume_text: str):
    """
    Called in a background thread. Stages:
    1. Search  → find URLs
    2. Fetch   → get page content
    3. Extract → parse into structured JSON
    4. Match   → score vs resume
    5. Done
    """
    try:
        # Stage 1 — Search
        update_run(run_id, status="running", stage="Searching job portals...", progress=5)
        raw_hits = search_all_portals(role, location)
        if not raw_hits:
            update_run(run_id, status="failed", stage="No jobs found — try different search terms")
            return
        update_run(run_id, stage=f"Found {len(raw_hits)} URLs. Fetching content...", progress=20)

        # Stage 2+3 — Fetch + Extract
        extracted_jobs = []
        for i, hit in enumerate(raw_hits):
            prog = 20 + int((i / len(raw_hits)) * 40)
            update_run(run_id, stage=f"Extracting job {i+1}/{len(raw_hits)}: {hit['title'][:40]}...", progress=prog)

            content = fetch_job_content(hit["url"])
            if not content:
                log.info(f"Skipping {hit['url']} — no content extracted")
                continue

            job_data = extract_job(content, hit["url"], hit["portal"])
            if job_data:
                extracted_jobs.append(job_data)

        if not extracted_jobs:
            update_run(run_id, status="failed", stage="Could not extract any job details")
            return

        update_run(run_id, stage=f"Extracted {len(extracted_jobs)} jobs. Matching against resume...", progress=65)

        # Stage 4 — Match + save to DB
        with get_conn() as conn:
            for job in extracted_jobs:
                score, reason = match_job(job, resume_text)
                conn.execute("""
                    INSERT OR IGNORE INTO jobs
                    (run_id, url, title, company, location, salary, portal, raw_text, match_score, match_reason)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (run_id, job.get("url",""), job.get("title",""), job.get("company",""),
                      job.get("location",""), job.get("salary",""), job.get("portal",""),
                      job.get("raw_text","")[:3000], score, reason))

        update_run(run_id, status="completed", stage="Done!", progress=100)
        log.info(f"Pipeline complete for run {run_id}")

    except Exception as e:
        log.error(f"Pipeline failed for run {run_id}: {e}", exc_info=True)
        update_run(run_id, status="failed", stage=f"Error: {str(e)[:100]}", progress=0)

def start_pipeline_async(role: str, location: str, resume_text: str) -> str:
    run_id = create_run(role, location)
    thread = threading.Thread(target=run_pipeline, args=(run_id, role, location, resume_text), daemon=True)
    thread.start()
    return run_id