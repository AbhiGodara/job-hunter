"""
Flask API server for Job Hunter Agent.
Serves the frontend and handles search, prep, and PDF download requests.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backend.utils.logger  # Hook up our logger on start

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from backend.storage.db import init_db, get_conn
from backend.resume.parser import parse_resume
from backend.pipeline.orchestrator import start_pipeline_async, get_run_status

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)
init_db()


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    """Start a fast scan pipeline. Returns run_id immediately."""
    data = request.form
    role       = data.get("role", "").strip()
    location   = data.get("location", "India").strip()
    experience = data.get("experience", "").strip()
    file       = request.files.get("resume")

    if not role:
        return jsonify({"error": "Role is required"}), 400
    if not file:
        return jsonify({"error": "Resume file is required"}), 400

    resume_text, quality = parse_resume(file)
    if quality < 0.3:
        return jsonify({"error": "Resume parsing quality too low. Please upload a text-based PDF or DOCX."}), 400

    run_id = start_pipeline_async(role, location, experience, resume_text)
    return jsonify({"run_id": run_id, "resume_quality": round(quality, 2)})


@app.route("/api/status/<run_id>")
def status(run_id):
    """Frontend polls this every 2s."""
    return jsonify(get_run_status(run_id))


@app.route("/api/prep/<int:job_id>", methods=["POST"])
def prep(job_id):
    """On-demand: generate tailored resume + research + interview prep for one job.
    This is the ONLY place where Groq LLM is called."""
    from backend.pipeline.rate_limiter import groq_client
    from backend.agents.resume_writer import write_resume
    from backend.agents.researcher import research_company
    from backend.agents.interview_prep import prep_interview
    from backend.agents.pdf_generator import generate_pdf

    with get_conn() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        run = None
        if job:
            run = conn.execute("SELECT * FROM job_runs WHERE id=?", (job["run_id"],)).fetchone()

    if not job or not run:
        return jsonify({"error": "Job not found"}), 404

    # Always use the properly parsed resume text stored in DB
    # (parsing was done by parse_resume on upload — no garbled binary)
    resume_text = ""
    if run:
        try:
            resume_text = run["resume_text"] or ""
        except Exception:
            resume_text = ""

    if not resume_text:
        return jsonify({"error": "Resume text not found. Please re-upload your resume."}), 400

    job_dict = dict(job)

    # Generate all three prep outputs using Groq
    resume_md    = write_resume(job_dict, resume_text)
    research_md  = research_company(job_dict)
    interview_md = prep_interview(job_dict, resume_text)

    # Generate PDFs
    safe_name = f"{job_dict.get('company', 'company')}_{job_id}".replace(" ", "_").lower()
    resume_pdf_path    = generate_pdf(resume_md, f"resume_{safe_name}.pdf", title="Tailored Resume")
    interview_pdf_path = generate_pdf(interview_md, f"interview_{safe_name}.pdf", title="Interview Prep")

    # Save to database
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO prep_outputs
            (job_id, resume_md, research_md, interview_md, resume_pdf, interview_pdf)
            VALUES (?,?,?,?,?,?)
        """, (
            job_id,
            resume_md,
            research_md,
            interview_md,
            resume_pdf_path,
            interview_pdf_path,
        ))

    return jsonify({
        "resume":    resume_md,
        "research":  research_md,
        "interview": interview_md,
        "resume_pdf":    f"/api/pdf/resume_{safe_name}.pdf" if resume_pdf_path else None,
        "interview_pdf": f"/api/pdf/interview_{safe_name}.pdf" if interview_pdf_path else None,
    })


@app.route("/api/pdf/<filename>")
def serve_pdf(filename):
    """Serve generated PDF files."""
    pdf_dir = os.path.join(os.path.dirname(__file__), "../data/pdfs")
    pdf_path = os.path.join(pdf_dir, filename)
    if not os.path.exists(pdf_path):
        return jsonify({"error": "PDF not found"}), 404
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/api/history")
def history():
    with get_conn() as conn:
        runs = conn.execute(
            "SELECT id, role, location, status, progress, created_at FROM job_runs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in runs])


if __name__ == "__main__":
    app.run(debug=True, port=5000)