/**
 * Renders job cards with structured JD sections, skill chips,
 * salary badges, and expandable details.
 */

function renderJobs(jobs) {
    const container = document.getElementById('jobs-grid');
    container.innerHTML = '';
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:2rem;">No matching jobs found. Try different keywords.</p>';
        return;
    }

    // Stats
    const companies = new Set(jobs.map(j => j.company));
    const portals = new Set(jobs.map(j => j.portal));

    // Portal colors
    const portalConfig = {
        'greenhouse': { bg: 'rgba(34, 197, 94, 0.12)',  color: '#4ade80', label: 'Greenhouse' },
        'ashby':      { bg: 'rgba(99, 102, 241, 0.12)', color: '#a78bfa', label: 'Ashby' },
        'lever':      { bg: 'rgba(245, 158, 11, 0.12)', color: '#fbbf24', label: 'Lever' },
        'playwright': { bg: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8', label: 'Career Site' },
        'web':        { bg: 'rgba(156, 163, 175, 0.12)', color: '#9ca3af', label: 'Web' },
    };

    jobs.forEach((job, idx) => {
        const relevance = Math.round((job.relevance || 0) * 100);
        let relevanceClass = 'low';
        if (relevance >= 70) relevanceClass = 'high';
        else if (relevance >= 40) relevanceClass = 'medium';

        const portal = portalConfig[job.portal] || portalConfig['web'];

        // Format posted date
        let postedLabel = '';
        if (job.posted_at) {
            const d = new Date(job.posted_at);
            if (!isNaN(d.getTime())) {
                const now = new Date();
                const diffDays = Math.round((now - d) / 86400000);
                postedLabel = diffDays === 0 ? 'today'
                    : diffDays === 1 ? '1 day ago'
                    : diffDays < 30 ? `${diffDays} days ago`
                    : job.posted_at;
            }
        }

        // Build chips
        let chipsHTML = `<span class="chip chip-portal" style="background:${portal.bg};color:${portal.color}">${portal.label}</span>`;
        if (postedLabel) {
            chipsHTML += `<span class="chip chip-date">${postedLabel}</span>`;
        }
        if (job.salary_range) {
            chipsHTML += `<span class="chip chip-salary">${job.salary_range}</span>`;
        }
        if (job.experience_level) {
            chipsHTML += `<span class="chip chip-exp">${job.experience_level}</span>`;
        }
        if (job.employment_type) {
            chipsHTML += `<span class="chip chip-type">${job.employment_type}</span>`;
        }

        // Skill chips (max 5)
        let skillChipsHTML = '';
        if (job.skills) {
            const skills = job.skills.split(',').map(s => s.trim()).filter(Boolean).slice(0, 5);
            skillChipsHTML = skills.map(s => `<span class="chip chip-skill">${s}</span>`).join('');
        }

        // Expandable details content
        let detailsHTML = '';
        const hasDetails = job.description || job.responsibilities || job.requirements || job.benefits;
        
        if (hasDetails) {
            detailsHTML += '<div class="job-details-inner">';
            if (job.description) {
                detailsHTML += `
                    <div class="detail-section">
                        <div class="detail-label">Job Description</div>
                        <div class="detail-text">${_truncate(job.description, 500)}</div>
                    </div>`;
            }
            if (job.requirements) {
                detailsHTML += `
                    <div class="detail-section">
                        <div class="detail-label">Requirements</div>
                        <div class="detail-text">${_truncate(job.requirements, 400)}</div>
                    </div>`;
            }
            if (job.responsibilities) {
                detailsHTML += `
                    <div class="detail-section">
                        <div class="detail-label">Responsibilities</div>
                        <div class="detail-text">${_truncate(job.responsibilities, 400)}</div>
                    </div>`;
            }
            if (job.benefits) {
                detailsHTML += `
                    <div class="detail-section">
                        <div class="detail-label">Benefits</div>
                        <div class="detail-text">${_truncate(job.benefits, 300)}</div>
                    </div>`;
            }
            detailsHTML += '</div>';
        }

        const card = document.createElement('div');
        card.className = 'glass-card job-card';
        card.innerHTML = `
            <div class="job-title">${_escapeHtml(job.title || 'Unknown Role')}</div>
            <div class="job-meta">
                <span>${_escapeHtml(job.company || 'Unknown')}</span>
                <span class="job-meta-divider">•</span>
                <span>${_escapeHtml(job.location || 'N/A')}</span>
            </div>
            <div class="relevance-section">
                <div class="relevance-bar">
                    <div class="relevance-fill ${relevanceClass}" style="width: ${relevance}%"></div>
                </div>
                <div class="relevance-label">${relevance}% match</div>
            </div>
            <div class="job-chips">${chipsHTML}</div>
            ${skillChipsHTML ? `<div class="job-chips">${skillChipsHTML}</div>` : ''}
            ${hasDetails ? `
                <button class="job-expand-toggle" data-idx="${idx}">
                    <span class="arrow">▶</span> View Details
                </button>
                <div class="job-details" id="job-details-${idx}">
                    ${detailsHTML}
                </div>
            ` : ''}
            <div class="job-actions">
                <a href="${job.url}" target="_blank" rel="noopener" class="btn btn-sm btn-outline">View Job ↗</a>
                <button class="btn btn-sm btn-primary prep-btn" data-id="${job.id}">Prep Me ✨</button>
            </div>
        `;
        container.appendChild(card);
    });

    // Summary
    document.getElementById('summary-text').textContent = 
        `Found ${jobs.length} jobs across ${companies.size} companies`;
    
    const metaEl = document.getElementById('results-meta');
    if (metaEl) {
        metaEl.textContent = `Sources: ${Array.from(portals).join(', ')} • Sorted by relevance`;
    }

    // Prep button handlers
    document.querySelectorAll('.prep-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const jobId = e.target.getAttribute('data-id');
            showPrepModal(jobId);
        });
    });

    // Expand toggle handlers
    document.querySelectorAll('.job-expand-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = btn.getAttribute('data-idx');
            const details = document.getElementById(`job-details-${idx}`);
            const isExpanded = details.classList.contains('expanded');
            
            if (isExpanded) {
                details.classList.remove('expanded');
                btn.classList.remove('expanded');
                btn.innerHTML = '<span class="arrow">▶</span> View Details';
            } else {
                details.classList.add('expanded');
                btn.classList.add('expanded');
                btn.innerHTML = '<span class="arrow">▶</span> Hide Details';
            }
        });
    });
}


function exportToCSV(jobs) {
    if (!jobs || jobs.length === 0) return;
    const headers = ['Title', 'Company', 'Location', 'Portal', 'Relevance', 'Salary', 'Experience', 'Skills', 'URL'];
    const rows = jobs.map(j => [
        `"${(j.title || '').replace(/"/g, '""')}"`,
        `"${(j.company || '').replace(/"/g, '""')}"`,
        `"${(j.location || '').replace(/"/g, '""')}"`,
        `"${(j.portal || '').replace(/"/g, '""')}"`,
        Math.round((j.relevance || 0) * 100) + '%',
        `"${(j.salary_range || '').replace(/"/g, '""')}"`,
        `"${(j.experience_level || '').replace(/"/g, '""')}"`,
        `"${(j.skills || '').replace(/"/g, '""')}"`,
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


function _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


function _truncate(text, maxLen) {
    if (!text) return '';
    const escaped = _escapeHtml(text);
    if (escaped.length <= maxLen) return escaped;
    return escaped.substring(0, maxLen) + '...';
}
