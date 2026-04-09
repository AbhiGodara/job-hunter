"""
SQLite-based cache manager for storing search results.
Provides get, set, and automatic cleanup of expired cache entries.
"""
import json
from datetime import datetime, timedelta
from backend.storage.db import get_conn
from backend.config import CACHE_TTL_HOURS

def get_cached(key: str):
    """Returns Python object or None if TTL expired / missing."""
    with get_conn() as conn:
        row = conn.execute("SELECT data, expires_at FROM cache WHERE cache_key=?", (key,)).fetchone()
        if not row:
            return None
            
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            # Expired, clean it up and return None
            conn.execute("DELETE FROM cache WHERE cache_key=?", (key,))
            conn.commit()
            return None
            
        return json.loads(row["data"])

def set_cached(key: str, data):
    """Stores JSON-serialized data with TTL expiry."""
    expires_at = datetime.now() + timedelta(hours=CACHE_TTL_HOURS)
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (cache_key, data, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), expires_at.isoformat())
        )
        conn.commit()

def clear_expired():
    """Deletes all expired cache entries. Call on app startup."""
    with get_conn() as conn:
        conn.execute("DELETE FROM cache WHERE expires_at < ?", (datetime.now().isoformat(),))
        conn.commit()
