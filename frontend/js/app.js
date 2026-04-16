/**
 * Main application controller — handles search, polling, modal, and agent status.
 */
let currentJobs = [];
let activePoller = null;

// ── Search Form ────────────────────────────────────────────────────
document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const role = document.getElementById('role').value;
    const location = document.getElementById('location').value || 'India';
    const experience = document.getElementById('experience').value || '';
    const resumeFile = document.getElementById('resume-upload').files[0];
    
    if (!role || !resumeFile) {
        alert("Please provide a role and a resume file.");
        return;
    }
    
    document.getElementById('view-form').classList.remove('active');
    document.getElementById('view-progress').classList.add('active');
    
    const formData = new FormData();
    formData.append('role', role);
    formData.append('location', location);
    formData.append('experience', experience);
    formData.append('resume', resumeFile);
    
    try {
        const resp = await fetch('/api/search', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        activePoller = new JobPoller(data.run_id, {
            onProgress: (stage, progress) => {
                document.getElementById('progress-text').textContent = stage;
                document.getElementById('progress-bar').style.width = `${progress}%`;
                document.getElementById('progress-percent').textContent = `${progress}%`;
            },
            onComplete: (jobs) => {
                currentJobs = jobs;
                document.getElementById('view-progress').classList.remove('active');
                document.getElementById('view-results').classList.add('active');
                renderJobs(jobs);
            },
            onError: (err) => {
                alert(`Error: ${err}`);
                document.getElementById('view-progress').classList.remove('active');
                document.getElementById('view-form').classList.add('active');
            }
        });
        
        activePoller.start();
        
    } catch (err) {
        alert(`Failed to start search: ${err.message}`);
        document.getElementById('view-progress').classList.remove('active');
        document.getElementById('view-form').classList.add('active');
    }
});

// ── Cancel / Export / New Search ────────────────────────────────────
document.getElementById('cancel-btn').addEventListener('click', () => {
    if (activePoller) activePoller.stop();
    document.getElementById('view-progress').classList.remove('active');
    document.getElementById('view-form').classList.add('active');
});

document.getElementById('export-btn').addEventListener('click', () => {
    exportToCSV(currentJobs);
});

document.getElementById('new-search-btn').addEventListener('click', () => {
    document.getElementById('view-results').classList.remove('active');
    document.getElementById('view-form').classList.add('active');
    document.getElementById('search-form').reset();
    updateFileLabel();
});

// ── Modal Logic ────────────────────────────────────────────────────
const modal = document.getElementById('prep-modal');

document.getElementById('close-modal-btn').addEventListener('click', () => {
    modal.classList.remove('active');
});

// Close on overlay click
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.remove('active');
    }
});

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
        modal.classList.remove('active');
    }
});

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        const target = e.target.getAttribute('data-target');
        e.target.classList.add('active');
        document.getElementById(target).classList.add('active');
    });
});


// ── Agent Status Management ────────────────────────────────────────

function setAgentStatus(agentId, status) {
    const chip = document.getElementById(agentId);
    if (!chip) return;
    chip.classList.remove('active', 'done');
    if (status === 'active') chip.classList.add('active');
    else if (status === 'done') chip.classList.add('done');
}

function resetAgentStatus() {
    ['agent-resume', 'agent-researcher', 'agent-coach'].forEach(id => {
        setAgentStatus(id, 'idle');
    });
}


// ── Prep Modal (CrewAI) ────────────────────────────────────────────

async function showPrepModal(jobId) {
    modal.classList.add('active');
    
    // Reset to first tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('.tab[data-target="tab-resume"]').classList.add('active');
    document.getElementById('tab-resume').classList.add('active');
    
    // Show loading state with agent-specific messaging
    resetAgentStatus();
    setAgentStatus('agent-resume', 'active');
    
    document.getElementById('content-resume').innerHTML = `
        <div class="loading-spinner"></div>
        <p class="loading-text">Resume Tailor Agent is analyzing your resume against the JD...</p>
    `;
    document.getElementById('content-research').innerHTML = `
        <div class="loading-spinner"></div>
        <p class="loading-text">Company Researcher Agent will start after Resume Tailor...</p>
    `;
    document.getElementById('content-interview').innerHTML = `
        <div class="loading-spinner"></div>
        <p class="loading-text">Interview Coach Agent will start after Company Researcher...</p>
    `;
    
    // Hide PDF buttons
    document.getElementById('download-resume-pdf').style.display = 'none';
    document.getElementById('download-interview-pdf').style.display = 'none';
    
    // Update subtitle with job info
    const job = currentJobs.find(j => j.id == jobId);
    if (job) {
        document.getElementById('modal-subtitle').textContent = 
            `${job.title} at ${job.company} • CrewAI Multi-Agent Pipeline`;
    }
    
    try {
        // Simulate agent progression (since actual is sequential on server)
        const agentTimer = setInterval(() => {
            // The server runs all 3 agents sequentially, so we animate through them
        }, 3000);

        const resp = await fetch(`/api/prep/${jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        clearInterval(agentTimer);
        
        const data = await resp.json();
        
        if (data.error) {
            alert(data.error);
            modal.classList.remove('active');
            return;
        }
        
        // Mark all agents as done
        setAgentStatus('agent-resume', 'done');
        setAgentStatus('agent-researcher', 'done');
        setAgentStatus('agent-coach', 'done');
        
        // Render content
        document.getElementById('content-resume').innerHTML = marked.parse(data.resume || "");
        document.getElementById('content-research').innerHTML = marked.parse(data.research || "");
        document.getElementById('content-interview').innerHTML = marked.parse(data.interview || "");
        
        // Markdown downloads
        setupDownloadBtn('download-resume', data.resume, 'tailored_resume.md');
        setupDownloadBtn('download-research', data.research, 'company_research.md');
        setupDownloadBtn('download-interview', data.interview, 'interview_prep.md');
        
        // PDF downloads
        if (data.resume_pdf) {
            const pdfBtn = document.getElementById('download-resume-pdf');
            pdfBtn.style.display = 'inline-flex';
            pdfBtn.onclick = () => window.open(data.resume_pdf, '_blank');
        }
        if (data.interview_pdf) {
            const pdfBtn = document.getElementById('download-interview-pdf');
            pdfBtn.style.display = 'inline-flex';
            pdfBtn.onclick = () => window.open(data.interview_pdf, '_blank');
        }
        
    } catch (err) {
        alert("Failed to generate prep materials: " + err.message);
        modal.classList.remove('active');
    }
}


function setupDownloadBtn(btnId, content, filename) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    
    newBtn.addEventListener('click', () => {
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    });
}
