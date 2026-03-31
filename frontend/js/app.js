/**
 * Job Hunter Agent — Frontend Application
 * Handles UI interactions, API communication, and SSE streaming.
 */

// ============================================================
// State
// ============================================================
const state = {
    resumeText: "",
    resumeFilename: "",
    selectedPortals: [],
    rankedJobs: [],
    searching: false,
};

// ============================================================
// DOM Elements
// ============================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
    position: $("#inp-position"),
    level: $("#inp-level"),
    location: $("#inp-location"),
    dateRange: $("#sel-date"),
    portalGrid: $("#portal-grid"),
    uploadZone: $("#upload-zone"),
    uploadSuccess: $("#upload-success"),
    uploadFilename: $("#upload-filename"),
    fileInput: $("#file-input"),
    resumeText: $("#inp-resume"),
    btnBrowse: $("#btn-browse"),
    btnRemoveFile: $("#btn-remove-file"),
    btnSearch: $("#btn-search"),
    btnHistory: $("#btn-history"),
    emptyState: $("#empty-state"),
    progressState: $("#progress-state"),
    progressTitle: $("#progress-title"),
    progressBar: $("#progress-bar"),
    progressMessage: $("#progress-message"),
    progressLog: $("#progress-log"),
    resultsState: $("#results-state"),
    resultsCount: $("#results-count"),
    resultsList: $("#results-list"),
    prepModal: $("#prep-modal"),
    prepModalTitle: $("#prep-modal-title"),
    prepLoading: $("#prep-loading"),
    prepLoadingMsg: $("#prep-loading-msg"),
    prepContent: $("#prep-content"),
    btnCloseModal: $("#btn-close-modal"),
    historyModal: $("#history-modal"),
    historyList: $("#history-list"),
    btnCloseHistory: $("#btn-close-history"),
};

// ============================================================
// Initialize
// ============================================================
async function init() {
    await loadPortals();
    bindEvents();
}

// ============================================================
// Load Portals
// ============================================================
async function loadPortals() {
    try {
        const res = await fetch("/api/portals");
        const portals = await res.json();

        els.portalGrid.innerHTML = portals
            .map(
                (p) => `
            <label class="portal-chip active" data-portal="${p.key}">
                <input type="checkbox" checked>
                <span class="portal-dot"></span>
                ${p.label.split("(")[0].trim()}
            </label>
        `
            )
            .join("");

        state.selectedPortals = portals.map((p) => p.key);

        // Bind chip clicks
        $$(".portal-chip").forEach((chip) => {
            chip.addEventListener("click", (e) => {
                e.preventDefault();
                chip.classList.toggle("active");
                const key = chip.dataset.portal;
                if (chip.classList.contains("active")) {
                    if (!state.selectedPortals.includes(key)) state.selectedPortals.push(key);
                } else {
                    state.selectedPortals = state.selectedPortals.filter((k) => k !== key);
                }
            });
        });
    } catch {
        els.portalGrid.innerHTML = '<p style="color:var(--error);font-size:0.82rem">Failed to load portals</p>';
    }
}

// ============================================================
// Event Bindings
// ============================================================
function bindEvents() {
    // File upload
    els.btnBrowse.addEventListener("click", () => els.fileInput.click());
    els.fileInput.addEventListener("change", handleFileSelect);
    els.btnRemoveFile.addEventListener("click", removeFile);

    // Drag & drop
    els.uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        els.uploadZone.classList.add("drag-over");
    });
    els.uploadZone.addEventListener("dragleave", () => {
        els.uploadZone.classList.remove("drag-over");
    });
    els.uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        els.uploadZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length) {
            els.fileInput.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });
    els.uploadZone.addEventListener("click", (e) => {
        if (e.target === els.btnBrowse || e.target.closest("#btn-browse")) return;
        els.fileInput.click();
    });

    // Search
    els.btnSearch.addEventListener("click", startSearch);

    // History
    els.btnHistory.addEventListener("click", showHistory);
    els.btnCloseHistory.addEventListener("click", () => els.historyModal.classList.add("hidden"));

    // Modal close
    els.btnCloseModal.addEventListener("click", () => els.prepModal.classList.add("hidden"));

    // Prep tabs
    $$(".prep-tab").forEach((tab) => {
        tab.addEventListener("click", () => switchPrepTab(tab.dataset.tab));
    });

    // Close modals on overlay click
    [els.prepModal, els.historyModal].forEach((modal) => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });
    });
}

// ============================================================
// File Upload
// ============================================================
async function handleFileSelect() {
    const file = els.fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        els.uploadZone.innerHTML = '<div class="spinner"></div><p class="upload-text">Parsing resume...</p>';

        const res = await fetch("/api/upload-resume", { method: "POST", body: formData });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            resetUploadZone();
            return;
        }

        state.resumeText = data.text;
        state.resumeFilename = data.filename;
        els.uploadFilename.textContent = `${data.filename} (${data.char_count} chars)`;
        els.uploadZone.classList.add("hidden");
        els.uploadSuccess.classList.remove("hidden");
        els.resumeText.value = data.text;
    } catch (err) {
        alert("Upload failed: " + err.message);
        resetUploadZone();
    }
}

function removeFile() {
    state.resumeText = "";
    state.resumeFilename = "";
    els.fileInput.value = "";
    els.uploadSuccess.classList.add("hidden");
    resetUploadZone();
    els.uploadZone.classList.remove("hidden");
    els.resumeText.value = "";
}

function resetUploadZone() {
    els.uploadZone.innerHTML = `
        <div class="upload-icon">📄</div>
        <p class="upload-text">Drag & drop your resume here</p>
        <p class="upload-hint">PDF, DOCX, or TXT (max 10MB)</p>
        <button class="btn btn-outline btn-sm" id="btn-browse" onclick="document.getElementById('file-input').click()">Browse Files</button>
    `;
}

// ============================================================
// Search
// ============================================================
function getResumeText() {
    return state.resumeText || els.resumeText.value.trim();
}

async function startSearch() {
    const resumeText = getResumeText();
    if (!resumeText) {
        alert("Please upload or paste your resume first.");
        return;
    }
    if (!els.position.value.trim()) {
        alert("Please enter a position/role.");
        return;
    }
    if (state.searching) return;

    state.searching = true;
    showProgress();

    const body = {
        position: els.position.value.trim(),
        level: els.level.value.trim(),
        location: els.location.value.trim(),
        resume_text: resumeText,
        portals: state.selectedPortals,
        date_range: els.dateRange.value,
    };

    try {
        const response = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleSSEEvent(event);
                    } catch { }
                }
            }
        }
    } catch (err) {
        updateProgress("Error: " + err.message, 0, "Error");
    } finally {
        state.searching = false;
    }
}

function handleSSEEvent(event) {
    switch (event.type) {
        case "progress":
            updateProgress(event.message, event.progress, event.phase);
            break;
        case "done":
            state.rankedJobs = event.jobs || [];
            showResults(state.rankedJobs, event.scraped_count);
            break;
        case "error":
            updateProgress("❌ " + event.message, 0, "Error");
            els.btnSearch.disabled = false;
            break;
    }
}

// ============================================================
// Progress UI
// ============================================================
function showProgress() {
    els.emptyState.classList.add("hidden");
    els.resultsState.classList.add("hidden");
    els.progressState.classList.remove("hidden");
    els.progressLog.innerHTML = "";
    els.btnSearch.disabled = true;
    updateProgress("Initializing search...", 0.02, "Starting");
}

function updateProgress(message, progress, phase) {
    els.progressTitle.textContent = formatPhase(phase);
    els.progressMessage.textContent = message;
    els.progressBar.style.width = `${Math.min(progress * 100, 100)}%`;

    const logEntry = document.createElement("p");
    logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    els.progressLog.appendChild(logEntry);
    els.progressLog.scrollTop = els.progressLog.scrollHeight;
}

function formatPhase(phase) {
    const map = {
        scraping: "🔍 Searching Job Portals",
        extracting: "🤖 AI Extracting Jobs",
        matching: "📊 AI Ranking Matches",
        Starting: "🚀 Starting",
        Error: "❌ Error",
    };
    return map[phase] || phase || "Processing...";
}

// ============================================================
// Results UI
// ============================================================
function showResults(jobs, scrapedCount) {
    els.progressState.classList.add("hidden");
    els.resultsState.classList.remove("hidden");
    els.btnSearch.disabled = false;

    els.resultsCount.textContent = `${jobs.length} jobs from ${scrapedCount || "?"} scraped`;

    if (!jobs.length) {
        els.resultsList.innerHTML = `
            <div class="empty-state" style="min-height:30vh">
                <div class="empty-icon">😕</div>
                <h2>No Matches Found</h2>
                <p>The AI couldn't rank any jobs. Try broadening your search or changing portals.</p>
            </div>
        `;
        return;
    }

    // Sort by score descending
    jobs.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));

    els.resultsList.innerHTML = jobs.map((job, i) => createJobCard(job, i)).join("");

    // Bind expand/collapse
    $$(".job-card-header").forEach((header) => {
        header.addEventListener("click", () => {
            header.closest(".job-card").classList.toggle("expanded");
        });
    });

    // Bind prep buttons
    $$(".btn-prep").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.index);
            openPrepModal(jobs[idx]);
        });
    });

    // Bind apply links
    $$(".btn-apply").forEach((btn) => {
        btn.addEventListener("click", (e) => e.stopPropagation());
    });
}

function createJobCard(job, index) {
    const score = job.match_score || "?";
    const title = job.job_title || "Unknown Position";
    const company = job.company_name || "Unknown Company";
    const location = job.job_location || "";
    const reason = job.reason || "";
    const url = job.job_posting_url || "#";
    const summary = job.job_summary || "";
    const remote = job.is_remote_friendly;
    const salary = job.compensation || "Not specified";
    const source = job.source_label || job.source || "";
    const employment = job.employment_type || "";

    return `
        <div class="job-card">
            <div class="job-card-header">
                <div class="job-card-info">
                    <div class="job-card-title">${escapeHtml(title)}</div>
                    <div class="job-card-company">${escapeHtml(company)}</div>
                    <div class="job-card-tags">
                        ${source ? `<span class="tag tag-source">${escapeHtml(source)}</span>` : ""}
                        ${location ? `<span class="tag tag-location">📍 ${escapeHtml(location)}</span>` : ""}
                        ${remote ? `<span class="tag tag-remote">🏠 Remote</span>` : ""}
                    </div>
                </div>
                <div class="job-card-score">
                    <div class="score-circle">${score}</div>
                    <span class="score-label">Match</span>
                </div>
            </div>
            <div class="job-card-body">
                ${reason ? `<div class="job-card-reason">${escapeHtml(reason)}</div>` : ""}
                <div class="job-card-details">
                    <div class="job-detail"><strong>Salary:</strong> ${escapeHtml(salary)}</div>
                    <div class="job-detail"><strong>Type:</strong> ${escapeHtml(employment || "N/A")}</div>
                </div>
                ${summary ? `<p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:1rem;line-height:1.5">${escapeHtml(summary)}</p>` : ""}
                <div class="job-card-actions">
                    <a href="${escapeHtml(url)}" target="_blank" class="btn btn-outline btn-sm btn-apply">Apply ↗</a>
                    <button class="btn btn-ghost btn-sm btn-prep" data-index="${index}">📝 Generate Prep Guide</button>
                </div>
            </div>
        </div>
    `;
}

// ============================================================
// Prep Guide Modal
// ============================================================
async function openPrepModal(job) {
    els.prepModal.classList.remove("hidden");
    els.prepLoading.classList.remove("hidden");
    els.prepContent.classList.add("hidden");
    els.prepModalTitle.textContent = `Prep: ${job.job_title || "Job"} @ ${job.company_name || "Company"}`;

    const resumeText = getResumeText();

    try {
        const response = await fetch("/api/prep", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ selected_job: job, resume_text: resumeText }),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === "progress") {
                            els.prepLoadingMsg.textContent = event.message;
                        } else if (event.type === "done") {
                            displayPrepResults(event.results);
                        } else if (event.type === "error") {
                            els.prepLoadingMsg.textContent = "❌ " + event.message;
                        }
                    } catch { }
                }
            }
        }
    } catch (err) {
        els.prepLoadingMsg.textContent = "❌ Error: " + err.message;
    }
}

function displayPrepResults(results) {
    els.prepLoading.classList.add("hidden");
    els.prepContent.classList.remove("hidden");

    $("#prep-tab-resume").innerHTML = formatMarkdown(results.resume || "No resume generated.");
    $("#prep-tab-research").innerHTML = formatMarkdown(results.research || "No research generated.");
    $("#prep-tab-interview").innerHTML = formatMarkdown(results.interview_prep || "No prep generated.");

    switchPrepTab("resume");
}

function switchPrepTab(tab) {
    $$(".prep-tab").forEach((t) => t.classList.remove("active"));
    $(`.prep-tab[data-tab="${tab}"]`).classList.add("active");

    $$(".prep-tab-content").forEach((c) => c.classList.add("hidden"));
    $(`#prep-tab-${tab}`).classList.remove("hidden");
}

// ============================================================
// History
// ============================================================
async function showHistory() {
    els.historyModal.classList.remove("hidden");
    els.historyList.innerHTML = '<div class="prep-loading"><div class="spinner"></div></div>';

    try {
        const res = await fetch("/api/history");
        const history = await res.json();

        if (!history.length) {
            els.historyList.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem">No search history yet.</p>';
            return;
        }

        els.historyList.innerHTML = history
            .map(
                (h) => `
            <div class="history-item" data-id="${h.search_id}">
                <div>
                    <div class="history-info">${escapeHtml(h.query?.level || "")} ${escapeHtml(h.query?.position || "")} in ${escapeHtml(h.query?.location || "")}</div>
                    <div class="history-date">${new Date(h.timestamp).toLocaleString()} · ${h.job_count} jobs</div>
                </div>
                <span class="badge">${h.job_count}</span>
            </div>
        `
            )
            .join("");

        $$(".history-item").forEach((item) => {
            item.addEventListener("click", () => loadHistoryItem(item.dataset.id));
        });
    } catch {
        els.historyList.innerHTML = '<p style="color:var(--error)">Failed to load history</p>';
    }
}

async function loadHistoryItem(searchId) {
    els.historyModal.classList.add("hidden");
    try {
        const res = await fetch(`/api/history/${searchId}`);
        const data = await res.json();
        if (data.jobs) {
            state.rankedJobs = data.jobs;
            showResults(data.jobs, data.raw_scraped_count);
        }
    } catch (err) {
        alert("Failed to load: " + err.message);
    }
}

// ============================================================
// Utilities
// ============================================================
function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatMarkdown(text) {
    if (!text) return "";
    // Basic markdown → HTML
    return text
        .replace(/^### (.*$)/gm, "<h3>$1</h3>")
        .replace(/^## (.*$)/gm, "<h2>$1</h2>")
        .replace(/^# (.*$)/gm, "<h1>$1</h1>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/^\- (.*$)/gm, "<li>$1</li>")
        .replace(/^\* (.*$)/gm, "<li>$1</li>")
        .replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>");
}

// ============================================================
// Boot
// ============================================================
document.addEventListener("DOMContentLoaded", init);
