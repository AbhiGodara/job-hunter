"""
Flask API server for the Job Hunter Agent.
Serves the frontend and provides REST API endpoints.
"""

import os
import sys
import json
import uuid
import queue
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

from flask import Flask, request, jsonify, send_from_directory, Response

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.scraper import search_jobs, PORTAL_QUERIES
from backend.resume_parser import parse_resume
from backend.crew import run_extraction, run_matching, run_prep

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB max upload

UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Active SSE tasks: task_id -> queue
active_tasks = {}


# ============================================================
# Static file serving
# ============================================================
@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "css"), filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "js"), filename)

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "assets"), filename)


# ============================================================
# API: Resume Upload
# ============================================================
@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt"):
        return jsonify({"error": f"Unsupported format: {ext}. Use PDF, DOCX, or TXT."}), 400

    safe_name = f"resume_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(file_path)

    try:
        text = parse_resume(file_path)
        if not text:
            return jsonify({"error": "Could not extract text from the file."}), 400
        return jsonify({
            "success": True,
            "filename": file.filename,
            "text": text,
            "char_count": len(text),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API: Available Portals
# ============================================================
@app.route("/api/portals", methods=["GET"])
def get_portals():
    portals = [{"key": k, "label": v["label"]} for k, v in PORTAL_QUERIES.items()]
    return jsonify(portals)


# ============================================================
# API: Search Jobs (SSE via background thread)
# ============================================================
@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    position = data.get("position", "").strip()
    location = data.get("location", "").strip()
    level = data.get("level", "").strip()
    resume_text = data.get("resume_text", "").strip()
    portals = data.get("portals", list(PORTAL_QUERIES.keys()))
    date_range = data.get("date_range", "1_month")

    if not position:
        return jsonify({"error": "Position is required"}), 400
    if not resume_text:
        return jsonify({"error": "Resume text is required"}), 400

    task_id = uuid.uuid4().hex[:12]
    msg_queue = queue.Queue()
    active_tasks[task_id] = msg_queue

    def emit(event_data):
        msg_queue.put(json.dumps(event_data))

    def run_pipeline():
        try:
            # Phase 1: Scrape
            def on_scrape_progress(msg, pct):
                emit({"type": "progress", "phase": "scraping", "message": msg, "progress": pct * 0.3})

            scraped = search_jobs(
                position=position,
                location=location,
                level=level,
                portals=portals,
                date_range=date_range,
                max_total=20,
                on_progress=on_scrape_progress,
            )

            if not scraped:
                emit({"type": "error", "message": "No jobs found. Try broadening your search."})
                return

            emit({"type": "progress", "phase": "scraping", "message": f"✅ Found {len(scraped)} jobs!", "progress": 0.3})

            # Build raw text for AI
            raw_job_data = ""
            for i, item in enumerate(scraped):
                raw_job_data += f"\n--- JOB {i+1} ---\n"
                raw_job_data += f"Title: {item['title']}\nURL: {item['url']}\nSource: {item['source_label']}\nContent:\n{item['content']}\n"

            # Phase 2: AI Extraction
            emit({"type": "progress", "phase": "extracting", "message": "AI is extracting job details...", "progress": 0.35})

            extracted_text = run_extraction(
                raw_job_data=raw_job_data,
                level=level,
                position=position,
                location=location,
                resume_text=resume_text,
            )

            emit({"type": "progress", "phase": "extracting", "message": "Extraction complete! Waiting for rate limit reset...", "progress": 0.55})

            # Phase 3: AI Matching
            emit({"type": "progress", "phase": "matching", "message": "AI is ranking jobs against your resume...", "progress": 0.6})

            ranked_jobs = run_matching(
                extracted_jobs_text=extracted_text,
                resume_text=resume_text,
            )

            # Save results
            search_id = uuid.uuid4().hex[:12]
            result_data = {
                "search_id": search_id,
                "timestamp": datetime.now().isoformat(),
                "query": {"position": position, "location": location, "level": level},
                "jobs": ranked_jobs,
                "raw_scraped_count": len(scraped),
            }
            result_path = os.path.join(DATA_DIR, f"search_{search_id}.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            emit({"type": "done", "search_id": search_id, "jobs": ranked_jobs, "scraped_count": len(scraped)})

        except Exception as e:
            emit({"type": "error", "message": str(e)[:500]})
        finally:
            emit(None)  # Sentinel to close the stream

    # Start pipeline in background
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    # Stream events from queue
    def event_stream():
        while True:
            try:
                msg = msg_queue.get(timeout=300)
                if msg is None:
                    break
                yield f"data: {msg}\n\n"
            except queue.Empty:
                break
        active_tasks.pop(task_id, None)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: Generate Prep Guide (SSE)
# ============================================================
@app.route("/api/prep", methods=["POST"])
def prep():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    selected_job = data.get("selected_job", {})
    resume_text = data.get("resume_text", "")

    if not selected_job:
        return jsonify({"error": "No job selected"}), 400

    task_id = uuid.uuid4().hex[:12]
    msg_queue = queue.Queue()

    def emit(event_data):
        msg_queue.put(json.dumps(event_data))

    def run_prep_pipeline():
        try:
            emit({"type": "progress", "message": "Starting prep guide generation...", "progress": 0.1})

            results = run_prep(
                selected_job_json=json.dumps(selected_job),
                resume_text=resume_text,
            )

            emit({"type": "done", "results": results})
        except Exception as e:
            emit({"type": "error", "message": str(e)[:500]})
        finally:
            emit(None)

    thread = threading.Thread(target=run_prep_pipeline, daemon=True)
    thread.start()

    def event_stream():
        while True:
            try:
                msg = msg_queue.get(timeout=600)
                if msg is None:
                    break
                yield f"data: {msg}\n\n"
            except queue.Empty:
                break

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: Search History
# ============================================================
@app.route("/api/history", methods=["GET"])
def get_history():
    history = []
    if os.path.exists(DATA_DIR):
        for fname in sorted(os.listdir(DATA_DIR), reverse=True):
            if fname.startswith("search_") and fname.endswith(".json"):
                try:
                    with open(os.path.join(DATA_DIR, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    history.append({
                        "search_id": data.get("search_id"),
                        "timestamp": data.get("timestamp"),
                        "query": data.get("query"),
                        "job_count": len(data.get("jobs", [])),
                    })
                except Exception:
                    pass
    return jsonify(history[:20])


@app.route("/api/history/<search_id>", methods=["GET"])
def get_search_result(search_id):
    fpath = os.path.join(DATA_DIR, f"search_{search_id}.json")
    if not os.path.exists(fpath):
        return jsonify({"error": "Search not found"}), 404
    with open(fpath, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


# ============================================================
# Run
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🎯 Job Hunter Agent — Server starting")
    print(f"   Frontend: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000, threaded=True)
