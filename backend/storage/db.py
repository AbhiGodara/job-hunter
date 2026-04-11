"""
SQLite storage for:
- job_runs: each pipeline execution
- jobs: extracted job records
- cache: search result cache with TTL
- prep_outputs: AI-generated prep materials
"""
import sqlite3, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/jobs.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS job_runs (
            id          TEXT PRIMARY KEY,
            role        TEXT,
            location    TEXT,
            experience  TEXT DEFAULT '',
            status      TEXT DEFAULT 'pending',
            stage       TEXT DEFAULT 'idle',
            progress    INTEGER DEFAULT 0,
            resume_text TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT REFERENCES job_runs(id),
            url         TEXT UNIQUE,
            title       TEXT,
            company     TEXT,
            location    TEXT,
            portal      TEXT,
            relevance   REAL DEFAULT 0,
            description TEXT DEFAULT '',
            extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,
            expires_at  DATETIME
        );

        CREATE TABLE IF NOT EXISTS prep_outputs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id       INTEGER REFERENCES jobs(id),
            resume_md    TEXT,
            research_md  TEXT,
            interview_md TEXT,
            resume_pdf   TEXT,
            interview_pdf TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Migration: add experience column if missing (for existing DBs)
        try:
            conn.execute("SELECT experience FROM job_runs LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE job_runs ADD COLUMN experience TEXT DEFAULT ''")

        # Migration: add description column if missing (for existing DBs)
        try:
            conn.execute("SELECT description FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE jobs ADD COLUMN description TEXT DEFAULT ''")

    print("DB initialized at", DB_PATH)