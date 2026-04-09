let currentJobs = [];
let resumeTextBackup = "";
let activePoller = null;

document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const role = document.getElementById('role').value;
    const location = document.getElementById('location').value || 'India';
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
                
                const reader = new FileReader();
                reader.onload = (e) => resumeTextBackup = e.target.result;
                reader.readAsText(resumeFile);
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

// Modal Logic
const modal = document.getElementById('prep-modal');
const closeBtn = document.querySelector('.close-modal');

closeBtn.addEventListener('click', () => {
    modal.classList.remove('active');
});

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        const target = e.target.getAttribute('data-target');
        e.target.classList.add('active');
        document.getElementById(target).classList.add('active');
    });
});

async function showPrepModal(jobId) {
    modal.classList.add('active');
    
    document.getElementById('content-resume').innerHTML = '<p>Generating tailored resume...</p>';
    document.getElementById('content-research').innerHTML = '<p>Generating company research...</p>';
    document.getElementById('content-interview').innerHTML = '<p>Generating interview prep...</p>';
    
    try {
        const resp = await fetch(`/api/prep/${jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resume_text: resumeTextBackup })
        });
        const data = await resp.json();
        
        if (data.error) {
            alert(data.error);
            modal.classList.remove('active');
            return;
        }
        
        document.getElementById('content-resume').innerHTML = marked.parse(data.resume || "");
        document.getElementById('content-research').innerHTML = marked.parse(data.research || "");
        document.getElementById('content-interview').innerHTML = marked.parse(data.interview || "");
        
        setupDownloadBtn('download-resume', data.resume, 'tailored_resume.md');
        setupDownloadBtn('download-research', data.research, 'company_research.md');
        setupDownloadBtn('download-interview', data.interview, 'interview_prep.md');
        
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
