import os
from dotenv import load_dotenv
load_dotenv()

# Groq API key pool — add 2-3 free keys for rotation
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]  # remove None values

# Model fallback chain — all free on Groq
LLM_MODELS = [
    "llama-3.3-70b-versatile",   # primary — best quality
    "mixtral-8x7b-32768",         # fallback 1 — fast
    "gemma2-9b-it",               # fallback 2 — lightweight
]

# Search settings
PORTALS = {
    "linkedin":   ("site:linkedin.com/jobs", 5),
    "indeed":     ("site:indeed.com", 5),
    "naukri":     ("site:naukri.com", 4),
    "glassdoor":  ("site:glassdoor.com", 4),
    "wellfound":  ("site:wellfound.com", 3),
    "simplyhired":("site:simplyhired.com", 3),
    "ats":        ("site:greenhouse.io OR site:lever.co OR site:jobs.ashbyhq.com", 5),
}

# Content fetcher
MIN_CONTENT_LENGTH = 300        # chars — below this, trigger Playwright fallback
PLAYWRIGHT_TIMEOUT  = 15000     # ms

# Rate limiter
GROQ_RPM_LIMIT      = 28        # leave 2 req buffer below actual 30 RPM
GROQ_COOLDOWN_SEC   = 65        # wait time after hitting limit
MAX_RETRIES         = 3

# Cache
CACHE_TTL_HOURS     = 6

# Pipeline
MAX_JOBS_PER_RUN    = 20
POLL_INTERVAL_SEC   = 2         # frontend polls every 2s