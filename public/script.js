document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const triggerBtn = document.getElementById('trigger-btn');
    const reportContent = document.getElementById('report-content');
    const reportTitle = document.getElementById('report-title');
    const reportTimestamp = document.getElementById('report-timestamp');
    
    // Chat DOM Elements
    const chatHistoryEl = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const quickSummaryBtn = document.getElementById('quick-summary-btn');

    let currentMode = 'stock';
    let currentReportText = '';
    let chatHistory = [];

    // Initialize Markdown parser
    marked.setOptions({ breaks: true, gfm: true });

    // Fetch report
    async function fetchReport(mode) {
        reportContent.innerHTML = '<p style="color: var(--text-muted);">Fetching latest report...</p>';
        chatHistory = []; // Reset chat on tab switch
        resetChatUI();

        try {
            const res = await fetch(`/api/report?mode=${mode}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            
            const text = await res.text();
            currentReportText = text;
            
            const lines = text.split('\n');
            let title = mode === 'stock' ? 'Stock Delivery Report' : 'ETF Swing Report';
            const h1Index = lines.findIndex(l => l.startsWith('# '));
            if (h1Index !== -1) {
                title = lines[h1Index].replace('# ', '').trim();
                lines.splice(h1Index, 1);
            }

            reportTitle.textContent = title;
            reportTimestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
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
            alert(`✅ Workflow triggered successfully!\nIt will take about 2-3 minutes. Refresh later.`);
        } catch (error) {
            alert(`❌ Error triggering workflow: ${error.message}`);
        } finally {
            triggerBtn.innerHTML = originalText;
            triggerBtn.disabled = false;
        }
    });

    // --- Chat Logic ---

    function resetChatUI() {
        chatHistoryEl.innerHTML = `
            <div class="chat-message assistant">
                <div class="message-bubble markdown-body">
                    <p>Hi! I'm ready to answer any questions about the current report. Or, click below to generate a quick summary!</p>
                    <button id="quick-summary-btn" class="btn btn-primary" style="margin-top: 10px;">Generate Summary</button>
                </div>
            </div>
        `;
        document.getElementById('quick-summary-btn').addEventListener('click', () => {
            sendChatMessage("Provide a concise, high-level summary of the market context, top entry candidates, and any critical warnings or exits. Format your response in clean markdown with bullet points. Keep it punchy and actionable.");
        });
    }

    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble markdown-body';
        
        if (role === 'assistant') {
            bubble.innerHTML = marked.parse(text);
        } else {
            bubble.textContent = text; // Plain text for user input
        }
        
        msgDiv.appendChild(bubble);
        chatHistoryEl.appendChild(msgDiv);
        chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
        
        return bubble;
    }

    async function sendChatMessage(text) {
        if (!text.trim() || !currentReportText) return;

        // Hide quick summary button if it exists
        const qBtn = document.getElementById('quick-summary-btn');
        if (qBtn) qBtn.style.display = 'none';

        // Add user message to UI and history
        appendMessage('user', text);
        chatHistory.push({ role: 'user', parts: [{ text }] });
        
        chatInput.value = '';
        sendBtn.disabled = true;
        chatInput.disabled = true;

        // Add loading bubble
        const loadingBubble = appendMessage('assistant', '...');

        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    reportText: currentReportText,
                    messages: chatHistory 
                })
            });
            
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.error || 'Failed to generate response');
            
            // Remove loading bubble
            chatHistoryEl.lastChild.remove();
            
            // Add AI response
            appendMessage('assistant', data.reply);
            chatHistory.push({ role: 'model', parts: [{ text: data.reply }] });

        } catch (error) {
            chatHistoryEl.lastChild.remove();
            appendMessage('assistant', `**Error:** ${error.message}`);
            // Remove the failed user message from history so they can retry
            chatHistory.pop();
        } finally {
            sendBtn.disabled = false;
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    sendBtn.addEventListener('click', () => {
        sendChatMessage(chatInput.value);
    });

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage(chatInput.value);
        }
    });

    // Handle Tabs
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            currentMode = btn.dataset.mode;
            fetchReport(currentMode);
        });
    });

    // Initial load
    fetchReport(currentMode);
});
