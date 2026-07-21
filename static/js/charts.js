// Chart.js Module for MikroTik Live Monitor 2.0 Turbo

let masterChart = null;
let bandwidthVivoChart = null;
let bandwidthMicksChart = null;

window.currentLatencyTab = 'todos'; // Default: merged multi-route view

// Color palette per destination (Best UI Design: neon-distinct colors)
const ROUTE_COLORS = {
    mm:  { vivo: '#9d4edd', micks: '#c77dff', name: 'MobileMed' },
    rbd: { vivo: '#00e676', micks: '#69f0ae', name: 'RBD PACS' },
    lf:  { vivo: '#ffb703', micks: '#ffd166', name: 'LifeFocus' },
    lp:  { vivo: '#fb8500', micks: '#f4a261', name: 'LifePlus' },
    ld:  { vivo: '#e040fb', micks: '#ea80fc', name: 'Laudite Portal' },
    lda: { vivo: '#ff007f', micks: '#ff5c9e', name: 'Laudite ASR' }
};

function createMergedDatasets() {
    const datasets = [];
    const keys = ['mm', 'rbd', 'lf', 'lp', 'lda'];
    keys.forEach(key => {
        const c = ROUTE_COLORS[key];
        datasets.push({
            label: `${c.name} VIVO`,
            data: [],
            borderColor: c.vivo,
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0.35,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 5,
            borderDash: []
        });
        datasets.push({
            label: `${c.name} MICKS`,
            data: [],
            borderColor: c.micks,
            backgroundColor: 'transparent',
            borderWidth: 1.5,
            tension: 0.35,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 5,
            borderDash: [5, 3]
        });
    });
    return datasets;
}

function createSingleDatasets() {
    return [
        {
            label: 'VIVO RTT (ms)',
            data: [],
            borderColor: '#8b5cf6',
            backgroundColor: 'rgba(139, 92, 246, 0.08)',
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 1,
            pointHoverRadius: 5
        },
        {
            label: 'MICKS RTT (ms)',
            data: [],
            borderColor: '#00d2fc',
            backgroundColor: 'rgba(0, 210, 252, 0.06)',
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 1,
            pointHoverRadius: 5
        }
    ];
}

function initMasterLatencyChart() {
    const ctx = document.getElementById('chart-master-latency');
    if (!ctx) return;
    
    masterChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: createMergedDatasets()
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#868e96',
                        font: { family: 'Plus Jakarta Sans', size: 11, weight: '600' },
                        usePointStyle: true,
                        pointStyle: 'line',
                        boxWidth: 20,
                        padding: 10
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(14, 16, 22, 0.95)',
                    titleColor: '#fff',
                    titleFont: { weight: '700', size: 13 },
                    bodyColor: '#a0aec0',
                    bodyFont: { size: 12 },
                    borderColor: 'rgba(139, 92, 246, 0.3)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 10,
                    callbacks: {
                        label: function(ctx) {
                            if (ctx.parsed.y <= 0) return null;
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} ms`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#868e96', font: { size: 10 }, maxTicksLimit: 8 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: {
                        color: '#868e96',
                        font: { size: 10 },
                        callback: function(value) { return value + ' ms'; }
                    }
                }
            }
        }
    });
}

function initBandwidthCharts() {
    const ctxVivo = document.getElementById('chart-bandwidth-vivo');
    const ctxMicks = document.getElementById('chart-bandwidth-micks');
    
    if (ctxVivo) {
        bandwidthVivoChart = new Chart(ctxVivo, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Download (RX Mbps)',
                        data: [],
                        borderColor: '#00d2fc',
                        backgroundColor: 'rgba(0, 210, 252, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    },
                    {
                        label: 'Upload (TX Mbps)',
                        data: [],
                        borderColor: '#ff007f',
                        backgroundColor: 'rgba(255, 0, 127, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    }
                ]
            },
            options: createBandwidthOptions()
        });
    }
    
    if (ctxMicks) {
        bandwidthMicksChart = new Chart(ctxMicks, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Download (RX Mbps)',
                        data: [],
                        borderColor: '#00d2fc',
                        backgroundColor: 'rgba(0, 210, 252, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    },
                    {
                        label: 'Upload (TX Mbps)',
                        data: [],
                        borderColor: '#ff007f',
                        backgroundColor: 'rgba(255, 0, 127, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    }
                ]
            },
            options: createBandwidthOptions()
        });
    }
}

function createBandwidthOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
            legend: {
                labels: { color: '#868e96', font: { family: 'Plus Jakarta Sans', size: 11, weight: '600' } }
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255,255,255,0.03)' },
                ticks: { color: '#868e96', font: { size: 9 }, maxTicksLimit: 6 }
            },
            y: {
                beginAtZero: true,
                grid: { color: 'rgba(255,255,255,0.03)' },
                ticks: { color: '#868e96', font: { size: 9 } }
            }
        }
    };
}

function setLatencySegment(tabKey) {
    window.currentLatencyTab = tabKey;
    document.querySelectorAll('.segment-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`btn-segment-${tabKey}`);
    if (activeBtn) activeBtn.classList.add('active');
    
    if (window.telemetryHistoryData) {
        updateMasterChartData(window.telemetryHistoryData);
    }
}

function updateMasterChartData(historyData) {
    if (!masterChart || !historyData) return;
    
    const tab = window.currentLatencyTab || 'todos';
    const labels = historyData.map(d => d.timestamp ? d.timestamp.split(' ')[1] || d.timestamp : '');
    
    if (tab === 'todos') {
        // Merged multi-route view: all destinations with distinct colors
        const keys = ['mm', 'rbd', 'lf', 'lp', 'lda'];
        const datasets = createMergedDatasets();
        
        keys.forEach((key, idx) => {
            const vivoData = historyData.map(d => d[`rtt_vivo_${key}`] || null);
            const micksData = historyData.map(d => d[`rtt_micks_${key}`] || null);
            // Replace 0 with null so chart.js skips the point
            datasets[idx * 2].data = vivoData.map(v => (v && v > 0) ? v : null);
            datasets[idx * 2 + 1].data = micksData.map(v => (v && v > 0) ? v : null);
        });
        
        masterChart.data.labels = labels;
        masterChart.data.datasets = datasets;
        masterChart.options.plugins.legend.display = true;
    } else {
        // Single destination view: VIVO vs MICKS only
        const vivoKey = `rtt_vivo_${tab}`;
        const micksKey = `rtt_micks_${tab}`;
        const vivoData = historyData.map(d => d[vivoKey] || 0);
        const micksData = historyData.map(d => d[micksKey] || 0);
        
        const datasets = createSingleDatasets();
        datasets[0].data = vivoData;
        datasets[1].data = micksData;
        
        masterChart.data.labels = labels;
        masterChart.data.datasets = datasets;
        masterChart.options.plugins.legend.display = true;
    }
    
    masterChart.update('none');
}

function updateBandwidthChartsData(historyData) {
    if (!historyData) return;
    
    const labels = historyData.map(d => d.timestamp ? d.timestamp.split(' ')[1] || d.timestamp : '');
    const vivoRx = historyData.map(d => ((d.traffic_vivo_rx || 0) / 1000000).toFixed(2));
    const vivoTx = historyData.map(d => ((d.traffic_vivo_tx || 0) / 1000000).toFixed(2));
    const micksRx = historyData.map(d => ((d.traffic_micks_rx || 0) / 1000000).toFixed(2));
    const micksTx = historyData.map(d => ((d.traffic_micks_tx || 0) / 1000000).toFixed(2));
    
    if (bandwidthVivoChart) {
        bandwidthVivoChart.data.labels = labels;
        bandwidthVivoChart.data.datasets[0].data = vivoRx;
        bandwidthVivoChart.data.datasets[1].data = vivoTx;
        bandwidthVivoChart.update('none');
    }
    
    if (bandwidthMicksChart) {
        bandwidthMicksChart.data.labels = labels;
        bandwidthMicksChart.data.datasets[0].data = micksRx;
        bandwidthMicksChart.data.datasets[1].data = micksTx;
        bandwidthMicksChart.update('none');
    }
}
