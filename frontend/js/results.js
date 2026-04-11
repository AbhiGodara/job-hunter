function renderJobs(jobs) {
    const container = document.getElementById('jobs-grid');
    container.innerHTML = '';
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p>No matching jobs found.</p>';
        return;
    }

    // Group by company for summary
    const companies = new Set(jobs.map(j => j.company));

    // Source tag colors
    const portalColors = {
        'greenhouse': 'rgba(34, 197, 94, 0.15)',
        'ashby':      'rgba(99, 102, 241, 0.15)',
        'lever':      'rgba(245, 158, 11, 0.15)',
        'web':        'rgba(236, 72, 153, 0.15)',
        'search':     'rgba(236, 72, 153, 0.15)',
    };

    jobs.forEach(job => {
        // Relevance as percentage
        const relevance = Math.round((job.relevance || 0) * 100);
        let relevanceClass = 'low';
        if (relevance >= 70) relevanceClass = 'high';
        else if (relevance >= 40) relevanceClass = 'medium';

        const portalLabel = job.portal === 'web' || job.portal === 'search' ? '🌐 Web' : job.portal;
        const tagBg = portalColors[job.portal] || 'rgba(255,255,255,0.1)';

        const card = document.createElement('div');
        card.className = 'glass-card job-card';
        card.innerHTML = `
            <div class="job-title">${job.title || 'Unknown Role'}</div>
            <div class="job-company">${job.company || 'Unknown Company'} • ${job.location || 'N/A'} • <span class="tag" style="background: ${tagBg}">${portalLabel}</span></div>
            <div class="relevance-bar">
                <div class="relevance-fill ${relevanceClass}" style="width: ${relevance}%"></div>
            </div>
            <div class="relevance-label">${relevance}% match</div>
            <div class="job-actions">
                <a href="${job.url}" target="_blank" class="btn btn-small btn-outline">View Job</a>
                <button class="btn btn-small prep-btn" data-id="${job.id}">Prep Me ✨</button>
            </div>
        `;
        container.appendChild(card);
    });

    document.getElementById('summary-text').textContent = 
        `Found ${jobs.length} jobs across ${companies.size} companies`;

    document.querySelectorAll('.prep-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const jobId = e.target.getAttribute('data-id');
            showPrepModal(jobId);
        });
    });
}

function exportToCSV(jobs) {
    if (!jobs || jobs.length === 0) return;
    const headers = ['Title', 'Company', 'Location', 'Portal', 'Relevance', 'URL'];
    const rows = jobs.map(j => [
        `"${(j.title || '').replace(/"/g, '""')}"`,
        `"${(j.company || '').replace(/"/g, '""')}"`,
        `"${(j.location || '').replace(/"/g, '""')}"`,
        `"${(j.portal || '').replace(/"/g, '""')}"`,
        Math.round((j.relevance || 0) * 100) + '%',
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
