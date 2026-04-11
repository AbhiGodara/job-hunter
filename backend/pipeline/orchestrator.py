"""
Pipeline orchestrator — coordinates the fast scan and prep phases.

Scan phase: Zero-token (fast_scanner.py handles everything)
Prep phase: On-demand Groq calls only when user clicks a specific job
"""
import uuid
import threading
import logging
from backend.storage.db import get_conn
from backend.pipeline.fast_scanner import fast_scan

log = logging.getLogger(__name__)


def create_run(role: str, location: str, experience: str, resume_text: str) -> str:
    """Create a new pipeline run entry in the database."""
    run_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO job_runs (id, role, location, experience, resume_text, status) VALUES (?,?,?,?,?,'pending')",
            (run_id, role, location, experience, resume_text),
        )
    return run_id


def update_run(run_id: str, **kwargs):
    """Update any field on a job_run row."""
    fields = ", ".join(f"{k}=?" for k in kwargs)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE job_runs SET {fields} WHERE id=?",
            (*kwargs.values(), run_id),
        )


def get_run_status(run_id: str) -> dict:
    """Returns current status, stage, progress, and jobs for a run."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM job_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return {"error": "run not found"}
        jobs = conn.execute(
            "SELECT id, title, company, location, url, portal, relevance "
            "FROM jobs WHERE run_id=? ORDER BY relevance DESC",
            (run_id,),
        ).fetchall()
        return {
            "run_id":   run_id,
            "status":   row["status"],
            "stage":    row["stage"],
            "progress": row["progress"],
            "jobs":     [dict(j) for j in jobs],
        }


def run_pipeline(run_id: str, role: str, location: str, experience: str, resume_text: str):
    """
    Fast scan pipeline — zero LLM tokens.
    1. Fetch jobs from ATS APIs (Greenhouse, Ashby, Lever) + DuckDuckGo
    2. Filter by title keywords
    3. Rank by role/location/experience relevance
    4. Save to DB
    """
    try:
        update_run(run_id, status="running", stage="Scanning company career pages...", progress=10)

        # Fast scan — no Groq calls!
        jobs = fast_scan(role, location, experience=experience, max_results=40)

        if not jobs:
            update_run(run_id, status="failed", stage="No matching jobs found — try different keywords")
            return

        update_run(run_id, stage=f"Found {len(jobs)} matching jobs. Saving...", progress=80)

        # Save to DB
        with get_conn() as conn:
            for job in jobs:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO jobs
                        (run_id, url, title, company, location, portal, relevance, description)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (
                        run_id,
                        job.get("url", ""),
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        job.get("portal", ""),
                        round(job.get("relevance", 0), 2),
                        job.get("description", "")[:500],
                    ))
                except Exception as e:
                    log.warning(f"Failed to insert job {job.get('url')}: {e}")

        update_run(run_id, status="completed", stage="Done!", progress=100)
        log.info(f"Pipeline complete for run {run_id}: {len(jobs)} jobs saved")

    except Exception as e:
        log.error(f"Pipeline failed for run {run_id}: {e}", exc_info=True)
        update_run(run_id, status="failed", stage=f"Error: {str(e)[:100]}", progress=0)


def start_pipeline_async(role: str, location: str, experience: str, resume_text: str) -> str:
    """Start the pipeline in a background thread. Returns run_id immediately."""
    run_id = create_run(role, location, experience, resume_text)
    thread = threading.Thread(
        target=run_pipeline,
        args=(run_id, role, location, experience, resume_text),
        daemon=True,
    )
    thread.start()
    return run_id