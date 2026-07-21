// Chart.js Module for MikroTik Live Monitor

let masterChart = null;
let bandwidthVivoChart = null;
let bandwidthMicksChart = null;

window.currentLatencyTab = 'mm'; // Default segment tab

function initMasterLatencyChart() {
    const ctx = document.getElementById('chart-master-latency');
    if (!ctx) return;
    
    masterChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
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
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#868e96',
                        font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#12141a',
                    titleColor: '#fff',
                    bodyColor: '#a0aec0',
                    borderColor: 'rgba(255,255,255,0.08)',
                    borderWidth: 1
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
                    ticks: { color: '#868e96', font: { size: 10 } }
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
    
    const tab = window.currentLatencyTab || 'mm';
    const vivoKey = `rtt_vivo_${tab}`;
    const micksKey = `rtt_micks_${tab}`;
    
    const labels = historyData.map(d => d.timestamp ? d.timestamp.split(' ')[1] || d.timestamp : '');
    const vivoData = historyData.map(d => d[vivoKey] || 0);
    const micksData = historyData.map(d => d[micksKey] || 0);
    
    masterChart.data.labels = labels;
    masterChart.data.datasets[0].data = vivoData;
    masterChart.data.datasets[1].data = micksData;
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
