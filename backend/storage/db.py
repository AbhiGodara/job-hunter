"""
SQLite storage for:
- job_runs: each pipeline execution
- jobs: extracted job records  
- cache: search result cache with TTL
"""
import sqlite3, json, os
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
            status      TEXT DEFAULT 'pending',
            stage       TEXT DEFAULT 'idle',
            progress    INTEGER DEFAULT 0,
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
            salary      TEXT,
            portal      TEXT,
            raw_text    TEXT,
            match_score INTEGER,
            match_reason TEXT,
            extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,
            expires_at  DATETIME
        );

        CREATE TABLE IF NOT EXISTS prep_outputs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      INTEGER REFERENCES jobs(id),
            resume_md   TEXT,
            research_md TEXT,
            interview_md TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
    print("DB initialized at", DB_PATH)