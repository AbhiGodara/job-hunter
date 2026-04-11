"""
Run the job-hunter Flask server.
Usage: python run.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from backend.server import app
from backend.storage.db import init_db

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    print(f"\n Job Hunter running at http://localhost:{port}\n")
    app.run(debug=debug, port=port, host="0.0.0.0")