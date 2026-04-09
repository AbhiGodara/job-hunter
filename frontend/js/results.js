function renderJobs(jobs) {
    const container = document.getElementById('jobs-grid');
    container.innerHTML = '';
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p>No matching jobs found.</p>';
        return;
    }

    let totalScore = 0;

    jobs.forEach(job => {
        totalScore += job.match_score;
        let starsHtml = '';
        for (let i = 1; i <= 5; i++) {
            starsHtml += `<span class="star ${i <= job.match_score ? 'filled' : ''}">★</span>`;
        }
        
        let matchReasonObj;
        try {
            matchReasonObj = typeof job.match_reason === 'string' ? job.match_reason : '';
        } catch { }

        const card = document.createElement('div');
        card.className = 'glass-card job-card';
        card.innerHTML = `
            <div class="job-title">${job.title || 'Unknown Role'}</div>
            <div class="job-company">${job.company || 'Unknown Company'} • ${job.location || ''} • <span class="tag">${job.portal}</span></div>
            <div class="job-score-container">${starsHtml}</div>
            <div class="job-reason">${matchReasonObj}</div>
            <div class="job-actions">
                <a href="${job.url}" target="_blank" class="btn btn-small btn-outline">Apply Now</a>
                <button class="btn btn-small prep-btn" data-id="${job.id}">Prep Me ✨</button>
            </div>
        `;
        container.appendChild(card);
    });

    const avgScore = totalScore / jobs.length;
    document.getElementById('summary-text').textContent = `Found ${jobs.length} jobs — Average match score: ${avgScore.toFixed(1)}/5`;

    document.querySelectorAll('.prep-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const jobId = e.target.getAttribute('data-id');
            showPrepModal(jobId);
        });
    });
}

function exportToCSV(jobs) {
    if (!jobs || jobs.length === 0) return;
    const headers = ['Title', 'Company', 'Location', 'Score', 'URL'];
    const rows = jobs.map(j => [
        `"${(j.title || '').replace(/"/g, '""')}"`,
        `"${(j.company || '').replace(/"/g, '""')}"`,
        `"${(j.location || '').replace(/"/g, '""')}"`,
        j.match_score,
        `"${(j.url || '').replace(/"/g, '""')}"`
    ]);
    
    const csvContent = "data:text/csv;charset=utf-8," 
        + headers.join(",") + "\n" 
        + rows.map(e => e.join(",")).join("\n");
        
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "job_hunter_results.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
