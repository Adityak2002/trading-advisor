document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const triggerBtn = document.getElementById('trigger-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const reportContent = document.getElementById('report-content');
    const reportTitle = document.getElementById('report-title');
    const reportTimestamp = document.getElementById('report-timestamp');
    
    const insightsContainer = document.getElementById('ai-insights-container');
    const insightsContent = document.getElementById('insights-content');
    const closeInsightsBtn = document.getElementById('close-insights');

    let currentMode = 'stock';
    let currentReportText = '';

    // Initialize Markdown parser options
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    // Fetch report
    async function fetchReport(mode) {
        reportContent.innerHTML = '<p style="color: var(--text-muted);">Fetching latest report...</p>';
        
        try {
            const res = await fetch(`/api/report?mode=${mode}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            
            const text = await res.text();
            currentReportText = text;
            
            // Extract title and render markdown
            const lines = text.split('\n');
            let title = mode === 'stock' ? 'Stock Delivery Report' : 'ETF Swing Report';
            
            // Try to grab the first H1
            const h1Index = lines.findIndex(l => l.startsWith('# '));
            if (h1Index !== -1) {
                title = lines[h1Index].replace('# ', '').trim();
                lines.splice(h1Index, 1); // Remove title from body
            }

            reportTitle.textContent = title;
            reportTimestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            // Parse remaining markdown
            reportContent.innerHTML = marked.parse(lines.join('\n'));
            
        } catch (error) {
            reportContent.innerHTML = `<div style="color: var(--danger);">Error loading report: ${error.message}</div>`;
        }
    }

    // Trigger workflow
    triggerBtn.addEventListener('click', async () => {
        triggerBtn.disabled = true;
        const originalText = triggerBtn.innerHTML;
        triggerBtn.innerHTML = 'Triggering...';
        
        try {
            const res = await fetch(`/api/trigger?mode=${currentMode}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            
            alert(`✅ ${currentMode.toUpperCase()} Workflow triggered successfully!\nIt will take about 2-3 minutes to run. The report will update automatically on refresh.`);
        } catch (error) {
            alert(`❌ Error triggering workflow: ${error.message}`);
        } finally {
            triggerBtn.innerHTML = originalText;
            triggerBtn.disabled = false;
        }
    });

    // Generate AI Insights
    analyzeBtn.addEventListener('click', async () => {
        if (!currentReportText) {
            alert("Please wait for the report to load first.");
            return;
        }

        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyzing...';
        insightsContainer.classList.remove('hidden');
        insightsContent.innerHTML = '<p>Gemini is reading the report...</p>';

        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reportText: currentReportText })
            });
            
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.error || 'Failed to generate insights');
            
            insightsContent.innerHTML = marked.parse(data.insights);
        } catch (error) {
            insightsContent.innerHTML = `<p style="color: var(--danger);">Error: ${error.message}</p><p style="font-size: 0.8rem; color: var(--text-muted);">Ensure GEMINI_API_KEY is set in Vercel environment variables.</p>`;
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Generate Insights';
        }
    });

    closeInsightsBtn.addEventListener('click', () => {
        insightsContainer.classList.add('hidden');
    });

    // Handle Tabs
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            currentMode = btn.dataset.mode;
            insightsContainer.classList.add('hidden');
            fetchReport(currentMode);
        });
    });

    // Initial load
    fetchReport(currentMode);
});
