/**
 * main.js - Client side logic for ShipFlow DBMS
 * Controls the Live SQL Activity Inspector drawer, modals, and real-time polling.
 */

document.addEventListener('DOMContentLoaded', () => {
    initSqlDrawer();
    startSqlLogsPolling();
});

// =============================================================================
// LIVE SQL INSPECTOR DRAWER CONTROLLER
// =============================================================================

function initSqlDrawer() {
    const toggleBtn = document.getElementById('toggleSqlDrawerBtn');
    const closeBtn = document.getElementById('closeSqlDrawerBtn');
    const overlay = document.getElementById('sqlDrawerOverlay');
    const drawer = document.getElementById('sqlDrawer');
    const clearBtn = document.getElementById('clearLogsBtn');

    if (!toggleBtn || !drawer) return;

    function openDrawer() {
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        fetchSqlLogs(); // Immediate fetch on open
    }

    function closeDrawer() {
        drawer.classList.add('translate-x-full');
        overlay.classList.add('hidden');
    }

    toggleBtn.addEventListener('click', openDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    if (overlay) overlay.addEventListener('click', closeDrawer);

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !drawer.classList.contains('translate-x-full')) {
            closeDrawer();
        }
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/sql-logs/clear', { method: 'POST' });
                fetchSqlLogs();
            } catch (err) {
                console.error("Failed to clear logs", err);
            }
        });
    }
}

// Global set of seen log IDs to avoid re-rendering if unchanged
let lastRenderedHash = "";

async function fetchSqlLogs() {
    try {
        const response = await fetch('/api/sql-logs?limit=35');
        if (!response.ok) return;
        const data = await response.json();

        // Update nav badge count
        const navBadge = document.getElementById('navSqlCountBadge');
        if (navBadge) {
            navBadge.textContent = `${data.total_operations} ops`;
        }

        const totalCountEl = document.getElementById('logTotalCount');
        if (totalCountEl) {
            totalCountEl.textContent = data.total_operations;
        }

        const streamEl = document.getElementById('sqlLogStream');
        if (!streamEl) return;

        if (!data.logs || data.logs.length === 0) {
            streamEl.innerHTML = `
                <div class="text-center py-12 text-slate-500 font-sans text-xs">
                    <i class="fa-solid fa-terminal text-2xl mb-2 text-slate-600 block"></i>
                    No recent database queries recorded yet. Perform an action in the UI!
                </div>
            `;
            return;
        }

        // Quick hash check to avoid dom rewriting when no new queries
        const currentHash = data.logs.map(l => l.id + l.timestamp).join('-');
        if (currentHash === lastRenderedHash) return;
        lastRenderedHash = currentHash;

        // Render query cards
        let html = '';
        data.logs.forEach(log => {
            const badgeClass = getBadgeColor(log.type);
            const statusIcon = log.status === 'SUCCESS' 
                ? '<i class="fa-solid fa-check text-emerald-400"></i>' 
                : '<i class="fa-solid fa-xmark text-rose-400"></i>';

            html += `
                <div class="bg-slate-950/80 border border-slate-800/80 hover:border-slate-700 rounded-lg p-3 transition-all">
                    <div class="flex items-center justify-between text-[11px] mb-1.5">
                        <div class="flex items-center space-x-1.5">
                            <span class="px-1.5 py-0.5 rounded font-bold text-[10px] tracking-wide uppercase ${badgeClass}">
                                ${escapeHtml(log.type)}
                            </span>
                            <span class="text-slate-400 text-[10px]">${log.timestamp}</span>
                        </div>
                        <div class="flex items-center space-x-2 text-[10px] text-slate-400 font-sans">
                            <span>${statusIcon} ${log.duration_ms}ms</span>
                            <span>•</span>
                            <span>${log.rows_affected} ${log.rows_affected === 1 ? 'row' : 'rows'}</span>
                        </div>
                    </div>
                    <div class="text-slate-200 text-[11px] leading-relaxed break-words bg-slate-900/90 p-2 rounded border border-slate-800 select-all">
                        <code>${escapeHtml(log.sql)}</code>
                    </div>
                    ${log.params ? `
                        <div class="mt-1 text-[10px] text-slate-400">
                            <span class="text-slate-500">Params:</span> <code class="text-amber-300/80">${escapeHtml(log.params)}</code>
                        </div>
                    ` : ''}
                    ${log.error ? `
                        <div class="mt-1 text-[10px] text-rose-400 bg-rose-950/40 p-1.5 rounded border border-rose-900/50">
                            Error: ${escapeHtml(log.error)}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        streamEl.innerHTML = html;

    } catch (e) {
        console.error("Error polling SQL logs:", e);
    }
}

function startSqlLogsPolling() {
    // Initial fetch
    fetchSqlLogs();
    // Poll every 2.5 seconds
    setInterval(fetchSqlLogs, 2500);
}

function getBadgeColor(type) {
    if (!type) return 'bg-slate-800 text-slate-300 border border-slate-700';
    if (type.startsWith('DDL')) return 'bg-amber-950 text-amber-300 border border-amber-800';
    if (type.includes('INSERT')) return 'bg-emerald-950 text-emerald-300 border border-emerald-800';
    if (type.includes('UPDATE')) return 'bg-blue-950 text-blue-300 border border-blue-800';
    if (type.includes('DELETE')) return 'bg-rose-950 text-rose-300 border border-rose-800';
    if (type.includes('SELECT')) return 'bg-indigo-950 text-indigo-300 border border-indigo-800';
    if (type.startsWith('TCL')) return 'bg-purple-950 text-purple-300 border border-purple-800';
    return 'bg-slate-800 text-slate-300 border border-slate-700';
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Modal Helper Utility
window.openModal = function(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('hidden');
};

window.closeModal = function(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
};
