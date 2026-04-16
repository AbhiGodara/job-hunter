"""
SQLite storage for:
- job_runs: each pipeline execution
- jobs: extracted job records with structured JD fields
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT REFERENCES job_runs(id),
            url             TEXT UNIQUE,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            portal          TEXT,
            relevance       REAL DEFAULT 0,
            description     TEXT DEFAULT '',
            salary_range    TEXT DEFAULT '',
            experience_level TEXT DEFAULT '',
            employment_type TEXT DEFAULT '',
            skills          TEXT DEFAULT '',
            responsibilities TEXT DEFAULT '',
            requirements    TEXT DEFAULT '',
            benefits        TEXT DEFAULT '',
            extracted_at    DATETIME DEFAULT CURRENT_TIMESTAMP
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

        # Migrations for existing databases
        _migrate(conn, "job_runs", "experience", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "description", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "salary_range", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "experience_level", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "employment_type", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "skills", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "responsibilities", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "requirements", "TEXT DEFAULT ''")
        _migrate(conn, "jobs", "benefits", "TEXT DEFAULT ''")

    print("DB initialized at", DB_PATH)


def _migrate(conn, table: str, column: str, col_type: str):
    """Safely add a column if it doesn't exist."""
    try:
        conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")