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
            if (u['7d']) {
                document.getElementById('vivo-uptime-7d').innerText = `${u['7d'].vivo_uptime}%`;
                document.getElementById('vivo-sla-7d').innerText = `${u['7d'].vivo_sla}%`;
                document.getElementById('micks-uptime-7d').innerText = `${u['7d'].micks_uptime}%`;
                document.getElementById('micks-sla-7d').innerText = `${u['7d'].micks_sla}%`;
            }
            if (u['30d']) {
                document.getElementById('vivo-uptime-30d').innerText = `${u['30d'].vivo_uptime}%`;
                document.getElementById('vivo-sla-30d').innerText = `${u['30d'].vivo_sla}%`;
                document.getElementById('micks-uptime-30d').innerText = `${u['30d'].micks_uptime}%`;
                document.getElementById('micks-sla-30d').innerText = `${u['30d'].micks_sla}%`;
            }
        }
    } catch (e) {
        console.error("Error fetching traffic stats:", e);
    }
}

async function fetchIncidents() {
    try {
        const res = await fetch('/api/incidents?days=7');
        if (!res.ok) return;
        const incidents = await res.json();
        
        const alertBanner = document.getElementById('active-alert-banner');
        if (incidents.length > 0) {
            const latest = incidents[0];
            const msgElem = document.getElementById('alert-banner-message');
            const timeElem = document.getElementById('alert-banner-time');
            if (msgElem) msgElem.innerText = `${latest.message} (${latest.rca || 'Sem RCA'})`;
            if (timeElem) timeElem.innerText = latest.timestamp;
            if (alertBanner) alertBanner.style.display = 'flex';
        } else {
            if (alertBanner) alertBanner.style.display = 'none';
        }
    } catch (e) {
        console.error("Error fetching incidents:", e);
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
