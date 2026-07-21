// Main Application Logic for MikroTik Live Monitor

window.currentTimeRange = '1h';
window.telemetryHistoryData = [];
let heartbeatTimer = null;
let pollTimer = null;
let heartbeatCounter = 0;

document.addEventListener('DOMContentLoaded', () => {
    initMasterLatencyChart();
    initBandwidthCharts();
    
    // Initial fetch
    fetchFullHistory(window.currentTimeRange);
    fetchTrafficStats();
    fetchIncidents();
    
    // 1.5s incremental polling loop
    pollTimer = setInterval(pollIncrementalLatest, 1500);
    
    // 5s Heartbeat progress animation
    startHeartbeatAnimation();
});

function startHeartbeatAnimation() {
    const circle = document.getElementById('heartbeat-progress');
    if (!circle) return;
    
    const maxOffset = 43.96; // 2 * pi * 7
    heartbeatCounter = 0;
    
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(() => {
        heartbeatCounter += 100;
        const progress = (heartbeatCounter % 1500) / 1500;
        const offset = maxOffset * (1 - progress);
        circle.style.strokeDashoffset = offset;
    }, 100);
}

function onTimeRangeChange(range) {
    window.currentTimeRange = range;
    fetchFullHistory(range);
}

async function fetchFullHistory(range) {
    let hours = 1;
    if (range === '12h') hours = 12;
    if (range === '24h') hours = 24;
    if (range === '7d') hours = 168;
    
    try {
        const res = await fetch(`/api/data?hours=${hours}`);
        if (!res.ok) return;
        const data = await res.json();
        
        window.telemetryHistoryData = data;
        if (data.length > 0) {
            const latest = data[data.length - 1];
            updateDashboardDOM(latest);
            updateMasterChartData(data);
            updateBandwidthChartsData(data);
            calculateSLAAndJitter(data);
        }
    } catch (e) {
        console.error("Error fetching full telemetry history:", e);
    }
}

async function pollIncrementalLatest() {
    try {
        const res = await fetch('/api/data/latest');
        if (!res.ok) return;
        const latest = await res.json();
        
        if (latest && latest.timestamp) {
            updateDashboardDOM(latest);
            
            // Append to local history if new
            const history = window.telemetryHistoryData || [];
            const lastHistory = history.length > 0 ? history[history.length - 1] : null;
            
            if (!lastHistory || lastHistory.id !== latest.id) {
                history.push(latest);
                if (history.length > 100) history.shift(); // keep sliding window
                updateMasterChartData(history);
                updateBandwidthChartsData(history);
                calculateSLAAndJitter(history);
            }
        }
    } catch (e) {
        console.error("Incremental poll error:", e);
    }
}

function updateDashboardDOM(data) {
    // 1. Link status card
    const cardRoute = document.getElementById('card-route');
    const nameElem = document.getElementById('active-link-name');
    const descElem = document.getElementById('active-link-desc');
    
    const activeLink = (data.link_ativo || 'VIVO').toUpperCase();
    if (cardRoute) {
        cardRoute.classList.remove('vivo-active', 'micks-active');
        if (activeLink === 'VIVO') {
            cardRoute.classList.add('vivo-active');
            if (nameElem) nameElem.innerHTML = '<span style="color: var(--accent-vivo);">VIVO FIBRA</span>';
            if (descElem) descElem.innerText = 'Operadora Principal Ativa (0ms failover)';
        } else {
            cardRoute.classList.add('micks-active');
            if (nameElem) nameElem.innerHTML = '<span style="color: var(--accent-micks);">MICKS TELECOM</span>';
            if (descElem) descElem.innerText = 'Operadora Backup Ativa (Rotas prioritárias)';
        }
    }
    
    // 2. Hardware metrics
    const cpuElem = document.getElementById('cpu-load');
    if (cpuElem) cpuElem.innerText = `${data.cpu || 0}%`;
    
    const tempElem = document.getElementById('cpu-temp');
    if (tempElem) tempElem.innerText = `${data.temp || 0}°C`;
    
    const uptimeElem = document.getElementById('router-uptime');
    if (uptimeElem) uptimeElem.innerText = data.uptime || '--:--:--';
    
    // 3. Bandwidth rates
    const lanRxMbps = ((data.traffic_lan_rx || 0) / 1000000).toFixed(2);
    const lanTxMbps = ((data.traffic_lan_tx || 0) / 1000000).toFixed(2);
    const totalLanMbps = (parseFloat(lanRxMbps) + parseFloat(lanTxMbps)).toFixed(2);
    
    const lanBwElem = document.getElementById('lan-bandwidth');
    if (lanBwElem) lanBwElem.innerHTML = `${totalLanMbps} <span style="font-size: 1rem;">Mbps</span>`;
    
    const vivoRxElem = document.getElementById('vivo-rx');
    if (vivoRxElem) vivoRxElem.innerText = `${((data.traffic_vivo_rx || 0) / 1000000).toFixed(2)} Mbps`;
    
    const vivoTxElem = document.getElementById('vivo-tx');
    if (vivoTxElem) vivoTxElem.innerText = `${((data.traffic_vivo_tx || 0) / 1000000).toFixed(2)} Mbps`;
    
    const micksRxElem = document.getElementById('micks-rx');
    if (micksRxElem) micksRxElem.innerText = `${((data.traffic_micks_rx || 0) / 1000000).toFixed(2)} Mbps`;
    
    const micksTxElem = document.getElementById('micks-tx');
    if (micksTxElem) micksTxElem.innerText = `${((data.traffic_micks_tx || 0) / 1000000).toFixed(2)} Mbps`;
    
    const lanRxElem = document.getElementById('lan-rx');
    if (lanRxElem) lanRxElem.innerText = `${lanRxMbps} Mbps`;
    
    const lanTxElem = document.getElementById('lan-tx');
    if (lanTxElem) lanTxElem.innerText = `${lanTxMbps} Mbps`;
    
    const vivoSpeedElem = document.getElementById('vivo-speed');
    if (vivoSpeedElem) vivoSpeedElem.innerText = data.eth1_speed || '1Gbps';
    
    const micksSpeedElem = document.getElementById('micks-speed');
    if (micksSpeedElem) micksSpeedElem.innerText = data.eth2_speed || '1Gbps';
    
    const vivoErrorsElem = document.getElementById('vivo-errors');
    if (vivoErrorsElem) vivoErrorsElem.innerText = data.eth1_errors || '0';
    
    const micksErrorsElem = document.getElementById('micks-errors');
    if (micksErrorsElem) micksErrorsElem.innerText = data.eth2_errors || '0';

    // 4. Radiology & Laudite Medical Health Metrics
    if (data.mos_laudite !== undefined) {
        const mosElem = document.getElementById('med-mos-laudite');
        if (mosElem) {
            const color = data.mos_laudite >= 4.0 ? 'var(--accent-green)' : (data.mos_laudite >= 3.5 ? 'var(--accent-orange)' : 'var(--accent-red)');
            mosElem.innerHTML = `<span style="color: ${color};">${data.mos_laudite} / 5.0 (${data.mos_status || 'Bom'})</span>`;
        }
    }
    
    if (data.laudite_asr_rtt_vivo !== undefined) {
        setElemText('laudite-asr-rtt-vivo', `${data.laudite_asr_rtt_vivo || 0} ms`);
    }
    if (data.laudite_asr_rtt_micks !== undefined) {
        setElemText('laudite-asr-rtt-micks', `${data.laudite_asr_rtt_micks || 0} ms`);
    }
    if (data.laudite_jitter !== undefined) {
        setElemText('laudite-jitter', `${data.laudite_jitter || 0} ms`);
    }
    
    if (data.ct_load_time_500mb) {
        setElemText('med-ct-load-time', data.ct_load_time_500mb);
    }
    if (data.mri_load_time_1gb) {
        setElemText('med-mri-load-time', data.mri_load_time_1gb);
    }
    
    if (data.best_routes && data.best_routes.lda) {
        const ldaBest = data.best_routes.lda;
        const winnerElem = document.getElementById('laudite-best-route-winner');
        if (winnerElem) {
            if (ldaBest.winner === 'VIVO') {
                winnerElem.innerHTML = `<span class="best-route-badge best-route-vivo"><i class="fa-solid fa-trophy"></i> VIVO FIBRA (${ldaBest.advantage_ms}ms mais rápida)</span>`;
            } else if (ldaBest.winner === 'MICKS') {
                winnerElem.innerHTML = `<span class="best-route-badge best-route-micks"><i class="fa-solid fa-trophy"></i> MICKS TELECOM (${ldaBest.advantage_ms}ms mais rápida)</span>`;
            } else {
                winnerElem.innerHTML = `<span class="best-route-badge best-route-tie">EMPATE TÉCNICO</span>`;
            }
        }
    }
    
    if (data.flapping_risk) {
        const flapElem = document.getElementById('med-flapping-risk');
        if (flapElem) {
            const isAlert = data.flapping_risk.includes('ALERTA');
            const color = isAlert ? 'var(--accent-red)' : 'var(--accent-green)';
            flapElem.innerHTML = `<span style="color: ${color};">${data.flapping_risk}</span>`;
        }
    }
    
    if (data.radiology_rca) {
        const rcaElem = document.getElementById('med-radiology-rca');
        if (rcaElem) {
            rcaElem.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--accent-green); margin-right: 0.3rem;"></i><span>${data.radiology_rca}</span>`;
        }
    }
}

async function fetchTrafficStats() {
    try {
        const res = await fetch('/api/traffic/stats?peak_days=30');
        if (!res.ok) return;
        const stats = await res.json();
        
        if (stats.today) {
            const vTodayGb = ((stats.today.vivo_rx + stats.today.vivo_tx) / 1073741824).toFixed(2);
            const mTodayGb = ((stats.today.micks_rx + stats.today.micks_tx) / 1073741824).toFixed(2);
            const vTodayRx = (stats.today.vivo_rx / 1073741824).toFixed(2);
            const vTodayTx = (stats.today.vivo_tx / 1073741824).toFixed(2);
            const mTodayRx = (stats.today.micks_rx / 1073741824).toFixed(2);
            const mTodayTx = (stats.today.micks_tx / 1073741824).toFixed(2);
            
            const vTodayElem = document.getElementById('vivo-today');
            if (vTodayElem) vTodayElem.innerText = `${vTodayRx} GB / ${vTodayTx} GB`;
            
            const mTodayElem = document.getElementById('micks-today');
            if (mTodayElem) mTodayElem.innerText = `${mTodayRx} GB / ${mTodayTx} GB`;
        }
        
        if (stats.month) {
            const vMonthRx = (stats.month.vivo_rx / 1073741824).toFixed(2);
            const vMonthTx = (stats.month.vivo_tx / 1073741824).toFixed(2);
            const mMonthRx = (stats.month.micks_rx / 1073741824).toFixed(2);
            const mMonthTx = (stats.month.micks_tx / 1073741824).toFixed(2);
            
            const vMonthElem = document.getElementById('vivo-month');
            if (vMonthElem) vMonthElem.innerText = `${vMonthRx} GB / ${vMonthTx} GB`;
            
            const mMonthElem = document.getElementById('micks-month');
            if (mMonthElem) mMonthElem.innerText = `${mMonthRx} GB / ${mMonthTx} GB`;
        }
        
        if (stats.peaks_table) {
            const vPeakRx = (stats.peaks_table.vivo_rx / 1000000).toFixed(2);
            const vPeakTx = (stats.peaks_table.vivo_tx / 1000000).toFixed(2);
            const mPeakRx = (stats.peaks_table.micks_rx / 1000000).toFixed(2);
            const mPeakTx = (stats.peaks_table.micks_tx / 1000000).toFixed(2);
            
            const vPeakElem = document.getElementById('vivo-peak');
            if (vPeakElem) vPeakElem.innerText = `${vPeakRx} / ${vPeakTx} Mbps`;
            
            const mPeakElem = document.getElementById('micks-peak');
            if (mPeakElem) mPeakElem.innerText = `${mPeakRx} / ${mPeakTx} Mbps`;
        }
        
        if (stats.uptime_report) {
            const u = stats.uptime_report;
            
            // Helper: color value based on percentage threshold
            function uptimeColor(val) {
                if (val >= 99.5) return 'var(--accent-green)';
                if (val >= 95) return '#ffb703';
                if (val >= 90) return 'var(--accent-orange)';
                return 'var(--accent-red)';
            }
            
            function setUptimeVal(id, val) {
                const el = document.getElementById(id);
                if (!el) return;
                el.innerText = `${val}%`;
                el.style.color = uptimeColor(val);
            }
            
            // 7d global summary
            if (u['7d']) {
                setUptimeVal('vivo-uptime-7d', u['7d'].vivo_uptime);
                setUptimeVal('vivo-sla-7d', u['7d'].vivo_sla);
                setUptimeVal('micks-uptime-7d', u['7d'].micks_uptime);
                setUptimeVal('micks-sla-7d', u['7d'].micks_sla);
                
                // Total samples badge
                const samplesEl = document.getElementById('uptime-total-samples');
                if (samplesEl) samplesEl.innerText = `📊 ${u['7d'].total_samples} amostras (7d)`;
                
                // Per-destination breakdown table
                const tbody = document.getElementById('uptime-dest-tbody');
                if (tbody && u['7d'].destinations) {
                    const dests = u['7d'].destinations;
                    const icons = {
                        mm: 'fa-hospital', rbd: 'fa-x-ray', lf: 'fa-eye',
                        lp: 'fa-circle-plus', lda: 'fa-microphone'
                    };
                    let html = '';
                    for (const [key, d] of Object.entries(dests)) {
                        const icon = icons[key] || 'fa-server';
                        
                        if (!d.has_data) {
                            html += `<tr style="opacity: 0.4;">
                                <td><div class="interface-name"><i class="fa-solid ${icon}" style="color: var(--text-muted); margin-right: 0.3rem;"></i>${d.name}</div></td>
                                <td colspan="7" style="text-align: center; color: var(--text-muted); font-style: italic;">Sem dados coletados neste período</td>
                                <td style="text-align: center;"><span class="bandwidth-badge" style="color: var(--text-muted); border-color: rgba(255,255,255,0.08); background: rgba(255,255,255,0.02);">N/A</span></td>
                            </tr>`;
                            continue;
                        }
                        
                        // Determine overall status
                        const bestSla = Math.max(d.vivo_sla, d.micks_sla);
                        let statusBadge = '';
                        if (bestSla >= 99) {
                            statusBadge = '<span class="bandwidth-badge" style="color: var(--accent-green); border-color: rgba(52,199,89,0.2); background: rgba(52,199,89,0.05);">✅ EXCELENTE</span>';
                        } else if (bestSla >= 95) {
                            statusBadge = '<span class="bandwidth-badge" style="color: var(--accent-green); border-color: rgba(52,199,89,0.2); background: rgba(52,199,89,0.05);">👍 BOM</span>';
                        } else if (bestSla >= 85) {
                            statusBadge = '<span class="bandwidth-badge" style="color: #ffb703; border-color: rgba(255,183,3,0.2); background: rgba(255,183,3,0.05);">⚠️ ATENÇÃO</span>';
                        } else {
                            statusBadge = '<span class="bandwidth-badge" style="color: var(--accent-red); border-color: rgba(255,59,48,0.2); background: rgba(255,59,48,0.05);">🔴 CRÍTICO</span>';
                        }
                        
                        html += `<tr>
                            <td><div class="interface-name"><i class="fa-solid ${icon}" style="color: var(--accent-vivo); margin-right: 0.3rem;"></i>${d.name}</div></td>
                            <td style="text-align: center; color: ${uptimeColor(d.vivo_uptime)}; font-weight: 700;">${d.vivo_uptime}%</td>
                            <td style="text-align: center; color: ${uptimeColor(d.vivo_sla)}; font-weight: 700;">${d.vivo_sla}%</td>
                            <td style="text-align: center; color: var(--text-muted);">${d.vivo_avg_rtt > 0 ? d.vivo_avg_rtt + ' ms' : '--'}</td>
                            <td style="text-align: center; color: ${uptimeColor(d.micks_uptime)}; font-weight: 700;">${d.micks_uptime}%</td>
                            <td style="text-align: center; color: ${uptimeColor(d.micks_sla)}; font-weight: 700;">${d.micks_sla}%</td>
                            <td style="text-align: center; color: var(--text-muted);">${d.micks_avg_rtt > 0 ? d.micks_avg_rtt + ' ms' : '--'}</td>
                            <td style="text-align: center; font-size: 0.78rem; color: var(--text-muted);">V≤${d.vivo_sla_limit}ms / M≤${d.micks_sla_limit}ms</td>
                            <td style="text-align: center;">${statusBadge}</td>
                        </tr>`;
                    }
                    tbody.innerHTML = html;
                }
            }
            
            // 30d summary footer
            if (u['30d']) {
                setUptimeVal('vivo-uptime-30d', u['30d'].vivo_uptime);
                setUptimeVal('vivo-sla-30d', u['30d'].vivo_sla);
                setUptimeVal('micks-uptime-30d', u['30d'].micks_uptime);
                setUptimeVal('micks-sla-30d', u['30d'].micks_sla);
            }
        }
    } catch (e) {
        console.error("Error fetching traffic stats:", e);
    }
}

async function fetchIncidents() {
    try {
        const res = await fetch('/api/incidents?days=7&limit=200');
        if (!res.ok) return;
        const incidents = await res.json();
        
        // Store globally for filtering
        window._allIncidents = incidents;
        window._incidentDays = 7;
        window._incidentTypeFilter = 'ALL';
        
        // Update alert banner with latest HIGH severity incident
        const alertBanner = document.getElementById('active-alert-banner');
        const highIncidents = incidents.filter(i => i.severity === 'HIGH');
        if (highIncidents.length > 0) {
            const latest = highIncidents[0];
            const msgElem = document.getElementById('alert-banner-message');
            const timeElem = document.getElementById('alert-banner-time');
            if (msgElem) msgElem.innerText = `${latest.message} (${latest.rca || 'Sem RCA'})`;
            if (timeElem) timeElem.innerText = latest.timestamp;
            if (alertBanner) alertBanner.style.display = 'flex';
        } else {
            if (alertBanner) alertBanner.style.display = 'none';
        }
        
        // Update count badge
        const badge = document.getElementById('incident-count-badge');
        if (badge) badge.innerText = incidents.length;
        
        // Initial render
        renderIncidentList(incidents);
    } catch (e) {
        console.error("Error fetching incidents:", e);
    }
}

function toggleIncidentLog() {
    const body = document.getElementById('incident-log-body');
    const chevron = document.getElementById('incident-log-chevron');
    if (!body) return;
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (chevron) chevron.style.transform = 'rotate(180deg)';
        // Load fresh data on first open
        if (!window._allIncidents || window._allIncidents.length === 0) {
            loadIncidents(1);
        }
    } else {
        body.style.display = 'none';
        if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
}

async function loadIncidents(days) {
    window._incidentDays = days;
    
    // Update period buttons
    ['24h', '7d', '30d'].forEach(k => {
        const btn = document.getElementById(`btn-inc-${k}`);
        if (btn) btn.classList.remove('active');
    });
    const map = { 1: '24h', 7: '7d', 30: '30d' };
    const activeBtn = document.getElementById(`btn-inc-${map[days]}`);
    if (activeBtn) activeBtn.classList.add('active');
    
    try {
        const res = await fetch(`/api/incidents?days=${days}&limit=500`);
        if (!res.ok) return;
        const incidents = await res.json();
        window._allIncidents = incidents;
        
        const badge = document.getElementById('incident-count-badge');
        if (badge) badge.innerText = incidents.length;
        
        filterIncidentType(window._incidentTypeFilter || 'ALL');
    } catch (e) {
        console.error("Error loading incidents:", e);
    }
}

function filterIncidentType(type) {
    window._incidentTypeFilter = type;
    
    // Update type filter buttons
    const typeMap = { 'ALL': 'all', 'LINK_FAILOVER': 'failover', 'LATENCY_SPIKE': 'latency', 'DESTINATION_DOWN': 'down', 'CPU_OVERLOAD': 'cpu' };
    Object.values(typeMap).forEach(k => {
        const btn = document.getElementById(`btn-inc-${k}`);
        if (btn) btn.classList.remove('active');
    });
    const activeBtn = document.getElementById(`btn-inc-${typeMap[type]}`);
    if (activeBtn) activeBtn.classList.add('active');
    
    let filtered = window._allIncidents || [];
    if (type !== 'ALL') {
        filtered = filtered.filter(i => i.type === type);
    }
    
    renderIncidentList(filtered);
}

function renderIncidentList(incidents) {
    const container = document.getElementById('incident-list');
    const summary = document.getElementById('incident-summary');
    if (!container) return;
    
    if (!incidents || incidents.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
                <i class="fa-solid fa-shield-check" style="font-size: 2.5rem; color: var(--accent-green); margin-bottom: 0.8rem; display: block;"></i>
                <div style="font-size: 0.95rem; font-weight: 600; color: var(--accent-green); margin-bottom: 0.3rem;">Nenhum Incidente Registrado</div>
                <div style="font-size: 0.78rem;">Rede operando com estabilidade total no período selecionado.</div>
            </div>`;
        if (summary) summary.innerHTML = '';
        return;
    }
    
    const typeConfig = {
        'LINK_FAILOVER': { icon: 'fa-shuffle', color: '#ff3b30', label: 'FAILOVER' },
        'LATENCY_SPIKE': { icon: 'fa-chart-line', color: '#ffb703', label: 'LATÊNCIA' },
        'DESTINATION_DOWN': { icon: 'fa-plug-circle-xmark', color: '#ff3b30', label: 'QUEDA' },
        'CPU_OVERLOAD': { icon: 'fa-microchip', color: '#ff9500', label: 'CPU' }
    };
    const severityConfig = {
        'HIGH': { bg: 'rgba(255,59,48,0.1)', border: 'rgba(255,59,48,0.25)', color: '#ff3b30', label: 'ALTA' },
        'MEDIUM': { bg: 'rgba(255,183,3,0.1)', border: 'rgba(255,183,3,0.25)', color: '#ffb703', label: 'MÉDIA' },
        'INFO': { bg: 'rgba(52,199,89,0.08)', border: 'rgba(52,199,89,0.2)', color: '#34c759', label: 'INFO' }
    };
    
    let html = '';
    incidents.forEach(inc => {
        const tc = typeConfig[inc.type] || { icon: 'fa-circle-exclamation', color: '#868e96', label: inc.type };
        const sc = severityConfig[inc.severity] || severityConfig['INFO'];
        
        // Time formatting
        let timeStr = inc.timestamp || '--';
        try {
            const d = new Date(inc.timestamp + 'Z');
            const now = new Date();
            const diffMs = now - d;
            const diffMin = Math.floor(diffMs / 60000);
            const diffHrs = Math.floor(diffMs / 3600000);
            
            if (diffMin < 60) timeStr = `${diffMin}min atrás`;
            else if (diffHrs < 24) timeStr = `${diffHrs}h atrás`;
            else timeStr = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
        } catch(e) {}
        
        html += `
        <div class="incident-row" style="display: flex; align-items: flex-start; gap: 0.8rem; padding: 0.8rem; border-radius: 12px; background: ${sc.bg}; border: 1px solid ${sc.border}; margin-bottom: 0.5rem; transition: all 0.2s;">
            <div style="min-width: 32px; height: 32px; border-radius: 8px; background: rgba(0,0,0,0.2); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                <i class="fa-solid ${tc.icon}" style="color: ${tc.color}; font-size: 0.85rem;"></i>
            </div>
            <div style="flex: 1; min-width: 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.25rem;">
                    <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
                        <span style="background: rgba(0,0,0,0.3); color: ${tc.color}; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-weight: 800; letter-spacing: 0.5px;">${tc.label}</span>
                        <span style="background: rgba(0,0,0,0.3); color: ${sc.color}; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-weight: 700;">${sc.label}</span>
                    </div>
                    <span style="font-size: 0.68rem; color: var(--text-muted); font-weight: 600; white-space: nowrap;">${timeStr}</span>
                </div>
                <div style="font-size: 0.82rem; color: var(--text-main); font-weight: 500; line-height: 1.4;">${inc.message}</div>
                ${inc.rca ? `<div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 0.2rem;"><i class="fa-solid fa-magnifying-glass" style="margin-right: 0.2rem;"></i>${inc.rca}</div>` : ''}
            </div>
        </div>`;
    });
    
    container.innerHTML = html;
    
    // Summary counters
    if (summary) {
        const counts = {};
        incidents.forEach(i => { counts[i.type] = (counts[i.type] || 0) + 1; });
        
        let sumHtml = '<div style="display: flex; gap: 1rem; flex-wrap: wrap;">';
        for (const [type, count] of Object.entries(counts)) {
            const tc = typeConfig[type] || { icon: 'fa-circle', color: '#868e96', label: type };
            sumHtml += `<span style="font-size: 0.72rem; color: ${tc.color}; display: flex; align-items: center; gap: 0.3rem;">
                <i class="fa-solid ${tc.icon}"></i> ${count} ${tc.label}
            </span>`;
        }
        sumHtml += '</div>';
        sumHtml += `<span style="font-size: 0.68rem; color: var(--text-muted);">${incidents.length} eventos no período</span>`;
        summary.innerHTML = sumHtml;
    }
}

function calculateSLAAndJitter(history) {
    if (!history || history.length === 0) return;
    
    const destinations = [
        { key: 'mm', name: 'MobileMed', slaLimit: 150 },
        { key: 'rbd', name: 'RBD PACS', slaLimit: 150 },
        { key: 'lf', name: 'LifeFocus', slaLimit: 280 },
        { key: 'lp', name: 'LifePlus', slaLimit: 280 },
        { key: 'ld', name: 'Laudite Portal', slaLimit: 250 },
        { key: 'lda', name: 'Laudite ASR', slaLimit: 250 }
    ];
    
    destinations.forEach(dest => {
        let vivoVals = history.map(d => d[`rtt_vivo_${dest.key}`] || 0).filter(v => v > 0);
        let micksVals = history.map(d => d[`rtt_micks_${dest.key}`] || 0).filter(v => v > 0);
        
        // Fallback: Laudite Portal (ld) uses Laudite ASR (lda) data if no portal data
        if (dest.key === 'ld' && vivoVals.length === 0) {
            vivoVals = history.map(d => d['rtt_vivo_lda'] || 0).filter(v => v > 0);
        }
        if (dest.key === 'ld' && micksVals.length === 0) {
            micksVals = history.map(d => d['rtt_micks_lda'] || 0).filter(v => v > 0);
        }
        
        const totalCount = history.length;
        const vivoLossPct = totalCount > 0 ? (((totalCount - vivoVals.length) / totalCount) * 100).toFixed(1) : '0.0';
        const micksLossPct = totalCount > 0 ? (((totalCount - micksVals.length) / totalCount) * 100).toFixed(1) : '0.0';
        
        const vivoAvg = vivoVals.length > 0 ? (vivoVals.reduce((a,b) => a+b, 0) / vivoVals.length).toFixed(1) : '0.0';
        const micksAvg = micksVals.length > 0 ? (micksVals.reduce((a,b) => a+b, 0) / micksVals.length).toFixed(1) : '0.0';
        
        const vivoJitter = calcJitter(vivoVals);
        const micksJitter = calcJitter(micksVals);
        
        // Update DOM elements
        setElemText(`sla-vivo-rtt-${dest.key}`, `${vivoAvg} ms`);
        setElemText(`sla-vivo-jitter-${dest.key}`, `${vivoJitter} ms`);
        setElemText(`sla-vivo-loss-${dest.key}`, `${vivoLossPct}%`);
        
        setElemText(`sla-micks-rtt-${dest.key}`, `${micksAvg} ms`);
        setElemText(`sla-micks-jitter-${dest.key}`, `${micksJitter} ms`);
        setElemText(`sla-micks-loss-${dest.key}`, `${micksLossPct}%`);
        
        // SLA Status badge — neutral for 0.0ms (no data), green for conforming, red for violation
        const isVivoOk = parseFloat(vivoAvg) > 0 && parseFloat(vivoAvg) <= dest.slaLimit;
        const isMicksOk = parseFloat(micksAvg) > 0 && parseFloat(micksAvg) <= dest.slaLimit;
        const hasAnyData = parseFloat(vivoAvg) > 0 || parseFloat(micksAvg) > 0;
        const statusElem = document.getElementById(`sla-status-${dest.key}`);
        const rowElem = document.getElementById(`sla-row-${dest.key}`);
        
        if (statusElem) {
            if (isVivoOk || isMicksOk) {
                statusElem.innerHTML = `<span class="bandwidth-badge" style="color: var(--accent-green); border-color: rgba(52,199,89,0.2); background: rgba(52,199,89,0.05);">EM CONFORMIDADE</span>`;
                if (rowElem) rowElem.classList.remove('sla-violation-row');
            } else if (!hasAnyData) {
                statusElem.innerHTML = `<span class="bandwidth-badge" style="color: var(--text-muted); border-color: rgba(255,255,255,0.1); background: rgba(255,255,255,0.03);">SEM DADOS</span>`;
                if (rowElem) rowElem.classList.remove('sla-violation-row');
            } else {
                statusElem.innerHTML = `<span class="bandwidth-badge" style="color: var(--accent-red); border-color: rgba(255,59,48,0.2); background: rgba(255,59,48,0.05);">VIOLAÇÃO SLA</span>`;
                if (rowElem) rowElem.classList.add('sla-violation-row');
            }
        }

        // Best Route Winner badge
        const bestElem = document.getElementById(`sla-best-route-${dest.key}`);
        if (bestElem) {
            const vVal = parseFloat(vivoAvg);
            const mVal = parseFloat(micksAvg);
            if (vVal > 0 && (mVal <= 0 || vVal < mVal - 2.0)) {
                bestElem.innerHTML = `<span class="best-route-badge best-route-vivo"><i class="fa-solid fa-trophy"></i> VIVO FIBRA</span>`;
            } else if (mVal > 0 && (vVal <= 0 || mVal < vVal - 2.0)) {
                bestElem.innerHTML = `<span class="best-route-badge best-route-micks"><i class="fa-solid fa-trophy"></i> MICKS TELECOM</span>`;
            } else if (vVal > 0 || mVal > 0) {
                bestElem.innerHTML = `<span class="best-route-badge best-route-tie">EMPATE</span>`;
            } else {
                bestElem.innerHTML = `<span class="best-route-badge best-route-tie">--</span>`;
            }
        }
    });
}

function calcJitter(vals) {
    if (vals.length < 2) return '0.0';
    let diffSum = 0;
    for (let i = 1; i < vals.length; i++) {
        diffSum += Math.abs(vals[i] - vals[i-1]);
    }
    return (diffSum / (vals.length - 1)).toFixed(1);
}

function setElemText(id, txt) {
    const elem = document.getElementById(id);
    if (elem) elem.innerText = txt;
}

function openGuideModal() {
    const modal = document.getElementById('guide-modal');
    if (modal) modal.style.display = 'flex';
}

function closeGuideModal() {
    const modal = document.getElementById('guide-modal');
    if (modal) modal.style.display = 'none';
}
