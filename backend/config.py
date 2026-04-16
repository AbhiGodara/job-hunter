"""
Central configuration for Job Hunter Agent.
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ── Fast Scanner ─────────────────────────────────────────────────────
MAX_RESULTS_PER_SCAN = 40       # Max jobs to show on UI
MIN_RESULTS_BEFORE_FALLBACK = 10  # If fewer, trigger DuckDuckGo
CACHE_TTL_HOURS = 6

# ── Groq API (used for CrewAI agents during prep phase) ─────────────
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]

# Model fallback chain
LLM_MODELS = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

# Rate limiter
GROQ_RPM_LIMIT = 28
GROQ_COOLDOWN_SEC = 30
MAX_RETRIES = 5

# ── RAG Settings ─────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_COLLECTION_PREFIX = "resume_"