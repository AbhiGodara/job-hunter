import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend.utils.logger # Hook up our logger on start

from flask import Flask, request, jsonify
from flask_cors import CORS
from backend.storage.db import init_db
from backend.resume.parser import parse_resume
from backend.pipeline.orchestrator import start_pipeline_async, get_run_status
from backend.agents.resume_writer import write_resume
from backend.agents.researcher import research_company
from backend.agents.interview_prep import prep_interview
from backend.storage.db import get_conn

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)
init_db()

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/search", methods=["POST"])
def search():
    """Start a pipeline run. Returns run_id immediately."""
    data = request.form
    role     = data.get("role", "").strip()
    location = data.get("location", "India").strip()
    file     = request.files.get("resume")

    if not role:
        return jsonify({"error": "Role is required"}), 400
    if not file:
        return jsonify({"error": "Resume file is required"}), 400

    resume_text, quality = parse_resume(file)
    if quality < 0.3:
        return jsonify({"error": "Resume parsing quality too low. Please upload a text-based PDF or DOCX."}), 400

    run_id = start_pipeline_async(role, location, resume_text)
    return jsonify({"run_id": run_id, "resume_quality": round(quality, 2)})

@app.route("/api/status/<run_id>")
def status(run_id):
    """Frontend polls this every 2s."""
    return jsonify(get_run_status(run_id))

@app.route("/api/prep/<int:job_id>", methods=["POST"])
def prep(job_id):
    """On-demand: generate resume + research + interview prep for one job."""
    with get_conn() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        run = conn.execute("SELECT * FROM job_runs WHERE id=?", (job["run_id"],)).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    resume_text = request.json.get("resume_text", "")
    result = {
        "resume":    write_resume(dict(job), resume_text),
        "research":  research_company(dict(job)),
        "interview": prep_interview(dict(job), resume_text)
    }
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO prep_outputs (job_id, resume_md, research_md, interview_md)
            VALUES (?,?,?,?)
        """, (job_id, result["resume"], result["research"], result["interview"]))

    return jsonify(result)

@app.route("/api/history")
def history():
    with get_conn() as conn:
        runs = conn.execute(
            "SELECT id, role, location, status, progress, created_at FROM job_runs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in runs])

if __name__ == "__main__":
    app.run(debug=True, port=5000)