import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.scraper.search_engine import build_query, search_duckduckgo
import logging
logging.basicConfig(level=logging.DEBUG)

queries = [
    build_query("ML engineer", "India", "site:naukri.com"),
    "ML engineer India site:naukri.com",
    "ML engineer India Naukri"
]

for q in queries:
    print("TESTING:", q)
    try:
        res = search_duckduckgo(q, 5)
        print("RESULTS:", len(res))
    except Exception as e:
        print("ERR:", e)
