document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const triggerBtn = document.getElementById('trigger-btn');
    const sendEmailBtn = document.getElementById('send-email-btn');
    const reportContent = document.getElementById('report-content');
    const reportTitle = document.getElementById('report-title');
    const reportTimestamp = document.getElementById('report-timestamp');
    
    // Action Console and Gauge DOM elements
    const laymanActionConsole = document.getElementById('layman-action-console');
    const visualPositionGauges = document.getElementById('visual-position-gauges');

    // Modal DOM Elements
    const logTradeBtn = document.getElementById('log-trade-btn');
    const logTradeModal = document.getElementById('log-trade-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const logTradeForm = document.getElementById('log-trade-form');
    const tradeMode = document.getElementById('trade-mode');
    const tradeTicker = document.getElementById('trade-ticker');
    const tradePrice = document.getElementById('trade-price');
    const tradeShares = document.getElementById('trade-shares');
    const tradeTarget = document.getElementById('trade-target');
    const tradeStop = document.getElementById('trade-stop');
    const tradeDate = document.getElementById('trade-date');

    // Chat DOM Elements
    const chatHistoryEl = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const quickSummaryBtn = document.getElementById('quick-summary-btn');
    
    // Mobile Responsive elements
    const mobileChatToggle = document.getElementById('mobile-chat-toggle');
    const chatCloseBtn = document.getElementById('chat-close-btn');
    const chatSidebar = document.querySelector('.chat-sidebar');
    const chatBadge = document.getElementById('chat-badge');

    let currentMode = 'stock';
    let currentReportText = '';
    let chatHistory = [];

    // Initialize Markdown parser
    marked.setOptions({ breaks: true, gfm: true });

    // Format utility
    function cleanCurrency(str) {
        if (!str) return '0.00';
        return str.replace(/[^\d.]/g, '');
    }

    // =============================================================================
    // REPORT MARKDOWN PARSER ENGINE
    // =============================================================================
    
    function parseCandidatesAndGauges(text, mode) {
        laymanActionConsole.innerHTML = '';
        visualPositionGauges.innerHTML = '';

        if (!text) return;

        // --- 1. Parse Entry Candidates ---
        const candidates = [];
        let sectionRegex = mode === 'intraday' 
            ? /### (🔼|🔽|▶) ([A-Z0-9.]+)\s*([\s\S]*?)(?=### (🔼|🔽|▶)|## |---)/g
            : /####? #(\d+) — ([A-Z0-9.]+)\s*([\s\S]*?)(?=####? #|## |---)/g;
            
        let match;
        const candidateTextSegment = text.split('## 🎯')[1] || text.split('## 🎯 Active Buy Signals')[1] || '';
        
        while ((match = sectionRegex.exec(candidateTextSegment)) !== null) {
            const ticker = (mode === 'intraday' ? match[2] : match[2]).trim();
            const body = match[3];
            
            let buyPrice = '0.00';
            let shares = '0';
            let invest = '0.00';
            let target = '0.00';
            let stop = '0.00';

            // Regex helpers for matching table cells
            const buyMatch = body.match(/Buy Price\*\* \| \*\*₹([\d,.]+)\*\*/i) || body.match(/Buy Trigger\*\* \| \*\*₹([\d,.]+)\*\*/i) || body.match(/Buy at.*limit.* \| \*\*₹([\d,.]+)\*\*/i);
            const sharesMatch = body.match(/Shares to Buy\*\* \| \*\*([\d,.]+)\*\*/i) || body.match(/Buy \*\*(\d+)\s+shares\*\*/i);
            const investMatch = body.match(/Investment Amount\*\* \| \*\*₹([\d,.]+)\*\*/i) || body.match(/Total Investment: \*\*₹([\d,.]+)\*\*/i);
            const targetMatch = body.match(/Target Price.*\| \*\*₹([\d,.]+)\*\*/i) || body.match(/Target \(Profit\)\*\* \| \*\*₹([\d,.]+)\*\*/i);
            const stopMatch = body.match(/Stop-Loss\*\* \| \*\*₹([\d,.]+)\*\*/i) || body.match(/Stop-Loss.*\| \*\*₹([\d,.]+)\*\*/i) || body.match(/Stop\s+\(Stop\)\*\* \| \*\*₹([\d,.]+)\*\*/i);

            if (buyMatch) buyPrice = cleanCurrency(buyMatch[1]);
            if (sharesMatch) shares = sharesMatch[1];
            if (investMatch) invest = cleanCurrency(investMatch[1]);
            if (targetMatch) target = cleanCurrency(targetMatch[1]);
            if (stopMatch) stop = cleanCurrency(stopMatch[1]);

            if (buyPrice !== '0.00') {
                candidates.push({
                    ticker,
                    action: 'BUY',
                    price: parseFloat(buyPrice),
                    shares: parseInt(shares, 10) || 0,
                    invest: parseFloat(invest) || (parseFloat(buyPrice) * (parseInt(shares, 10) || 0)),
                    target: parseFloat(target),
                    stop: parseFloat(stop)
                });
            }
        }

        // Render Action Console Cards
        if (candidates.length > 0) {
            const titleEl = document.createElement('h3');
            titleEl.style.fontSize = '0.9rem';
            titleEl.style.fontWeight = '700';
            titleEl.style.textTransform = 'uppercase';
            titleEl.style.color = 'var(--text-muted)';
            titleEl.style.letterSpacing = '0.05em';
            titleEl.style.marginBottom = '0.25rem';
            titleEl.textContent = '🟢 Recommended Actions';
            laymanActionConsole.appendChild(titleEl);

            candidates.forEach(c => {
                const card = document.createElement('div');
                card.className = 'action-card buy';
                card.innerHTML = `
                    <div class="action-card-header">
                        <span class="action-badge buy">Buy Signal</span>
                        <span class="action-ticker">${c.ticker}</span>
                    </div>
                    <div class="action-statement">
                        👉 <strong>What to do:</strong> Buy <strong>${c.shares} shares</strong> of <strong>${c.ticker.replace('.NS', '')}</strong> around <strong>₹${c.price.toFixed(2)}</strong>.
                    </div>
                    <div class="action-details-grid">
                        <div class="action-detail-item">
                            <span class="action-detail-label">Investment</span>
                            <span class="action-detail-value">₹${c.invest.toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                        </div>
                        <div class="action-detail-item">
                            <span class="action-detail-label">Take Profit Target</span>
                            <span class="action-detail-value" style="color: var(--success);">₹${c.target.toFixed(2)}</span>
                        </div>
                        <div class="action-detail-item">
                            <span class="action-detail-label">Stop-Loss Exit</span>
                            <span class="action-detail-value" style="color: var(--danger);">₹${c.stop.toFixed(2)}</span>
                        </div>
                    </div>
                    <div class="groww-action-strip">
                        <span class="groww-steps">Set GTT Target: ₹${c.target.toFixed(2)} | Stop-Loss: ₹${c.stop.toFixed(2)}</span>
                        <a href="https://groww.in/charts/${c.ticker.replace('.NS', '')}" target="_blank" class="btn btn-primary" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; border-radius: 8px;">Buy on Groww</a>
                    </div>
                `;
                laymanActionConsole.appendChild(card);
            });
        } else {
            // Idle state Card
            const card = document.createElement('div');
            card.className = 'action-card hold';
            card.innerHTML = `
                <div class="action-card-header">
                    <span class="action-badge hold">No New Signals</span>
                    <span class="action-ticker">IDLE режим</span>
                </div>
                <div class="action-statement" style="margin-bottom: 0;">
                    😴 <strong>All conditions stable:</strong> No entry setups meet the required threshold right now. Let your capital sit tight or hold existing positions.
                </div>
            `;
            laymanActionConsole.appendChild(card);
        }

        // --- 2. Parse Open Positions for Gauges ---
        const positions = [];
        const openPosSegment = text.split('## 📂 Open Positions')[1]?.split('---')[0] || '';
        
        // Find individual open position headers
        const posHeaders = openPosSegment.match(/### ([A-Z0-9.]+)/g) || [];
        const posBodies = openPosSegment.split(/### [A-Z0-9.]+/).slice(1);

        posHeaders.forEach((header, idx) => {
            const ticker = header.replace('### ', '').trim();
            const body = posBodies[idx] || '';

            // Extract position values
            const entryMatch = body.match(/Entry Price \| ₹?([\d,.]+)/i);
            const currentMatch = body.match(/Current Price \| ₹?([\d,.]+)/i);
            const targetMatch = body.match(/Target.*\| \*\*₹?([\d,.]+)\*\*/i);
            const stopMatch = body.match(/Stop-Loss \| \*\*₹?([\d,.]+)\*\*/i) || body.match(/Stop-Loss \| \*\*₹?([\d,.]+)\*\*.*breakeven/i);
            const pnlMatch = body.match(/P&L \| (📈|📉)\s+\*\*₹?([+-]?[\d,.]+)\s+\(([+-]?[\d,.]+%)\)\*\*/i);

            if (entryMatch && currentMatch && targetMatch && stopMatch) {
                const entry = parseFloat(cleanCurrency(entryMatch[1]));
                const current = parseFloat(cleanCurrency(currentMatch[1]));
                const target = parseFloat(cleanCurrency(targetMatch[1]));
                const stop = parseFloat(cleanCurrency(stopMatch[1]));
                const isProfit = pnlMatch ? pnlMatch[1] === '📈' : true;
                const pnlText = pnlMatch ? pnlMatch[2] : '0.00';
                const pnlPct = pnlMatch ? pnlMatch[3] : '0.0%';

                positions.push({
                    ticker, entry, current, target, stop, isProfit, pnlText, pnlPct
                });
            }
        });

        // Render Position Gauges
        if (positions.length > 0) {
            const titleEl = document.createElement('h3');
            titleEl.style.fontSize = '0.9rem';
            titleEl.style.fontWeight = '700';
            titleEl.style.textTransform = 'uppercase';
            titleEl.style.color = 'var(--text-muted)';
            titleEl.style.letterSpacing = '0.05em';
            titleEl.style.marginBottom = '0.25rem';
            titleEl.textContent = '💼 Active Position Tracking';
            visualPositionGauges.appendChild(titleEl);

            const grid = document.createElement('div');
            grid.className = 'visual-gauges-container';
            visualPositionGauges.appendChild(grid);

            positions.forEach(p => {
                // Calculate percentage position of current price on the slider (left=stop, right=target)
                let pct = 50; // default middle
                const range = p.target - p.stop;
                if (range > 0) {
                    pct = ((p.current - p.stop) / range) * 100;
                    pct = Math.max(0, Math.min(100, pct)); // clamp
                }
                
                // Calculate entry position pct
                let entryPct = 50;
                if (range > 0) {
                    entryPct = ((p.entry - p.stop) / range) * 100;
                }

                const card = document.createElement('div');
                card.className = 'gauge-card';
                card.innerHTML = `
                    <div class="gauge-header">
                        <span class="gauge-ticker">${p.ticker}</span>
                        <span class="gauge-pnl ${p.isProfit ? 'positive' : 'negative'}">
                            ${p.isProfit ? '▲' : '▼'} ₹${parseFloat(p.pnlText).toFixed(2)} (${p.pnlPct})
                        </span>
                    </div>
                    <div class="slider-gauge-wrapper">
                        <div class="slider-track">
                            <div class="slider-region stop" style="width: ${entryPct}%"></div>
                            <div class="slider-region target" style="left: ${entryPct}%; width: ${100 - entryPct}%"></div>
                            <div class="slider-marker" style="left: ${pct}%"></div>
                            
                            <span class="slider-label stop-limit" style="left: 0%;">₹${p.stop.toFixed(1)}</span>
                            <span class="slider-label entry" style="left: ${entryPct}%;">Buy: ₹${p.entry.toFixed(1)}</span>
                            <span class="slider-label target-limit" style="left: 100%;">₹${p.target.toFixed(1)}</span>
                        </div>
                    </div>
                    <div class="gauge-footer-stats">
                        <span>Current: <strong>₹${p.current.toFixed(2)}</strong></span>
                        <span>Status: <strong style="color: ${p.isProfit ? 'var(--success)' : 'var(--danger)'};">${p.isProfit ? 'In Profit' : 'In Drawdown'}</strong></span>
                    </div>
                `;
                grid.appendChild(card);
            });
        }
    }

    // =============================================================================
    // FETCH AND RENDER LOGIC
    // =============================================================================

    async function fetchReport(mode) {
        reportContent.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">Fetching latest report from GitHub...</p>';
        laymanActionConsole.innerHTML = '';
        visualPositionGauges.innerHTML = '';
        chatHistory = []; // Reset chat
        resetChatUI();

        try {
            const res = await fetch(`/api/report?mode=${mode}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            
            const text = await res.text();
            currentReportText = text;
            
            const lines = text.split('\n');
            let title = mode === 'stock' ? 'Stock Delivery Report' : mode === 'intraday' ? 'Intraday ORB Report' : 'ETF Swing Report';
            
            // Find title in markdown
            const h1Index = lines.findIndex(l => l.startsWith('# '));
            if (h1Index !== -1) {
                // If it's the Gemini AI Insights title, skip and check for next h1
                if (lines[h1Index].includes('Gemini AI Insights')) {
                    const secondH1Index = lines.slice(h1Index + 1).findIndex(l => l.startsWith('# '));
                    if (secondH1Index !== -1) {
                        title = lines[h1Index + 1 + secondH1Index].replace('# ', '').trim();
                    }
                } else {
                    title = lines[h1Index].replace('# ', '').trim();
                }
            }

            reportTitle.textContent = title;
            reportTimestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            // Render basic markdown report
            reportContent.innerHTML = marked.parse(text);
            
            // Run interactive parser to render Action Console and Gauges
            parseCandidatesAndGauges(text, mode);
            
        } catch (error) {
            reportContent.innerHTML = `<div style="color: var(--danger); text-align: center; padding: 2rem;">❌ Error loading report: ${error.message}</div>`;
        }
    }

    // =============================================================================
    // INTERACTIVE DIALOG MODAL (LOG GROWW TRADE)
    // =============================================================================
    
    // Autocalculate target and stop levels based on mode and entry price
    function autoCalculateLevels() {
        const price = parseFloat(tradePrice.value) || 0;
        const mode = tradeMode.value;

        if (price <= 0) {
            tradeTarget.value = '';
            tradeStop.value = '';
            return;
        }

        if (mode === 'stock') {
            tradeTarget.value = (price * 1.10).toFixed(4); // +10% target
            tradeStop.value = (price * 0.95).toFixed(4);   // default -5% stop if no ATR
        } else {
            tradeTarget.value = (price * 1.04).toFixed(4); // +4% target
            tradeStop.value = (price * 0.97).toFixed(4);   // default -3% stop if no ATR
        }
    }

    tradePrice.addEventListener('input', autoCalculateLevels);
    tradeMode.addEventListener('change', autoCalculateLevels);

    // Open Modal
    logTradeBtn.addEventListener('click', () => {
        // Pre-fill Date
        tradeDate.value = new Date().toISOString().split('T')[0];
        tradeMode.value = currentMode === 'intraday' ? 'stock' : currentMode;
        tradeTicker.value = '';
        tradePrice.value = '';
        tradeShares.value = '';
        tradeTarget.value = '';
        tradeStop.value = '';

        logTradeModal.style.display = 'flex';
        setTimeout(() => logTradeModal.classList.add('active'), 10);
    });

    // Close Modal helpers
    function closeModal() {
        logTradeModal.classList.remove('active');
        setTimeout(() => {
            logTradeModal.style.display = 'none';
        }, 300);
    }

    modalCloseBtn.addEventListener('click', closeModal);
    modalCancelBtn.addEventListener('click', closeModal);
    
    // Close on clicking overlay background
    logTradeModal.addEventListener('click', (e) => {
        if (e.target === logTradeModal) {
            closeModal();
        }
    });

    // Handle Form Submit
    logTradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = document.getElementById('modal-submit-btn');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';

        const payload = {
            mode: tradeMode.value,
            ticker: tradeTicker.value.trim(),
            entryPrice: parseFloat(tradePrice.value),
            shares: parseInt(tradeShares.value, 10),
            targetPrice: parseFloat(tradeTarget.value),
            stopPrice: parseFloat(tradeStop.value),
            entryDate: tradeDate.value
        };

        try {
            const res = await fetch('/api/update_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to save position');

            alert(data.message || 'Position saved successfully!');
            closeModal();
            // Refresh the current report mode
            fetchReport(currentMode);
        } catch (error) {
            alert(`❌ Error logging trade: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });

    // =============================================================================
    // EMAIL AND TRIGGER SCAN BUTTONS
    // =============================================================================

    sendEmailBtn.addEventListener('click', async () => {
        sendEmailBtn.disabled = true;
        sendEmailBtn.textContent = 'Sending...';

        try {
            const res = await fetch('/api/send_email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: currentMode })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            alert(data.message);
        } catch (error) {
            alert(`❌ Error sending email: ${error.message}`);
        } finally {
            sendEmailBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,12 2,6"/></svg> Send Email`;
            sendEmailBtn.disabled = false;
        }
    });

    triggerBtn.addEventListener('click', async () => {
        triggerBtn.disabled = true;
        const originalText = triggerBtn.innerHTML;
        triggerBtn.innerHTML = 'Triggering...';
        
        try {
            const res = await fetch(`/api/trigger?mode=${currentMode}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            alert(`✅ Action scan triggered successfully!\nGitHub Action is now running in the background (takes ~3 minutes). Refresh later.`);
        } catch (error) {
            alert(`❌ Error triggering scan: ${error.message}`);
        } finally {
            triggerBtn.innerHTML = originalText;
            triggerBtn.disabled = false;
        }
    });

    // =============================================================================
    // GEMINI CHAT BOT INTEGRATION
    // =============================================================================

    function resetChatUI() {
        chatHistoryEl.innerHTML = `
            <div class="chat-message assistant">
                <div class="message-bubble markdown-body">
                    <p>Hi Aditya! Ask me any questions about the current report setups, or click below for a quick AI summary.</p>
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
            bubble.textContent = text;
        }
        
        msgDiv.appendChild(bubble);
        chatHistoryEl.appendChild(msgDiv);
        chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
        
        return bubble;
    }

    async function sendChatMessage(text) {
        if (!text.trim() || !currentReportText) return;

        const qBtn = document.getElementById('quick-summary-btn');
        if (qBtn) qBtn.style.display = 'none';

        appendMessage('user', text);
        chatHistory.push({ role: 'user', parts: [{ text }] });
        
        chatInput.value = '';
        sendBtn.disabled = true;
        chatInput.disabled = true;

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
            
            chatHistoryEl.lastChild.remove();
            appendMessage('assistant', data.reply);
            chatHistory.push({ role: 'model', parts: [{ text: data.reply }] });

        } catch (error) {
            chatHistoryEl.lastChild.remove();
            appendMessage('assistant', `**Error:** ${error.message}`);
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
            
            chatSidebar.classList.remove('active');

            currentMode = btn.dataset.mode;
            fetchReport(currentMode);
        });
    });

    // Mobile Chat toggles
    if (mobileChatToggle && chatSidebar) {
        mobileChatToggle.addEventListener('click', () => {
            chatSidebar.classList.toggle('active');
            if (chatSidebar.classList.contains('active') && chatBadge) {
                chatBadge.style.display = 'none';
            }
        });
    }

    if (chatCloseBtn && chatSidebar) {
        chatCloseBtn.addEventListener('click', () => {
            chatSidebar.classList.remove('active');
        });
    }

    // Initial load
    fetchReport(currentMode);
});
