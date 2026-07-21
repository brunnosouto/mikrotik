import datetime
from db import get_db_connection

def calculate_traffic_stats(peak_days=30):
    tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
    today_str = datetime.datetime.now(tz_gmt3).strftime('%Y-%m-%d')
    month_prefix = datetime.datetime.now(tz_gmt3).strftime('%Y-%m')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Today accumulation
    cursor.execute('SELECT vivo_rx, vivo_tx, micks_rx, micks_tx FROM traffic_accumulation WHERE date = ?', (today_str,))
    row_today = cursor.fetchone()
    
    # 2. Month accumulation
    cursor.execute('SELECT SUM(vivo_rx), SUM(vivo_tx), SUM(micks_rx), SUM(micks_tx) FROM traffic_accumulation WHERE date LIKE ?', (month_prefix + '%',))
    row_month = cursor.fetchone()
    
    # 3. Peak traffic (24h)
    cursor.execute('''
        SELECT 
            MAX(traffic_vivo_rx), MAX(traffic_vivo_tx),
            MAX(traffic_micks_rx), MAX(traffic_micks_tx)
        FROM telemetry
        WHERE timestamp >= datetime('now', '-24 hours')
    ''')
    row_peaks_24h = cursor.fetchone()
    
    # 4. Peaks for selected interval
    cursor.execute('''
        SELECT 
            MAX(traffic_vivo_rx), MAX(traffic_vivo_tx),
            MAX(traffic_micks_rx), MAX(traffic_micks_tx),
            AVG(traffic_vivo_rx), AVG(traffic_vivo_tx),
            AVG(traffic_micks_rx), AVG(traffic_micks_tx)
        FROM telemetry
        WHERE timestamp >= datetime('now', ? || ' days')
    ''', (f"-{peak_days}",))
    row_peaks_table = cursor.fetchone()
    
    # 5. RTT Peaks (24h)
    cursor.execute('''
        SELECT 
            MAX(rtt_vivo_mm), MIN(CASE WHEN rtt_vivo_mm > 0 THEN rtt_vivo_mm END),
            MAX(rtt_micks_mm), MIN(CASE WHEN rtt_micks_mm > 0 THEN rtt_micks_mm END),
            
            MAX(rtt_vivo_lf), MIN(CASE WHEN rtt_vivo_lf > 0 THEN rtt_vivo_lf END),
            MAX(rtt_micks_lf), MIN(CASE WHEN rtt_micks_lf > 0 THEN rtt_micks_lf END),
            
            MAX(rtt_vivo_lp), MIN(CASE WHEN rtt_vivo_lp > 0 THEN rtt_vivo_lp END),
            MAX(rtt_micks_lp), MIN(CASE WHEN rtt_micks_lp > 0 THEN rtt_micks_lp END),
            
            MAX(rtt_vivo_laudite), MIN(CASE WHEN rtt_vivo_laudite > 0 THEN rtt_vivo_laudite END),
            MAX(rtt_micks_laudite), MIN(CASE WHEN rtt_micks_laudite > 0 THEN rtt_micks_laudite END),
            
            MAX(rtt_vivo_laudite_asr), MIN(CASE WHEN rtt_vivo_laudite_asr > 0 THEN rtt_vivo_laudite_asr END),
            MAX(rtt_micks_laudite_asr), MIN(CASE WHEN rtt_micks_laudite_asr > 0 THEN rtt_micks_laudite_asr END),
            
            MAX(rtt_vivo_rbd), MIN(CASE WHEN rtt_vivo_rbd > 0 THEN rtt_vivo_rbd END),
            MAX(rtt_micks_rbd), MIN(CASE WHEN rtt_micks_rbd > 0 THEN rtt_micks_rbd END)
        FROM telemetry
        WHERE timestamp >= datetime('now', '-24 hours')
    ''')
    row_rtt_peaks = cursor.fetchone()
    
    # 6. Fetch Uptime and SLA Compliance (7d & 30d)
    uptime_report = {}
    for name, days_limit in [('7d', 7), ('30d', 30)]:
        since_date = (datetime.datetime.now(tz_gmt3) - datetime.timedelta(days=days_limit)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT 
                COUNT(*),
                SUM(CASE WHEN rtt_vivo_mm > 0.0 OR rtt_vivo_lf > 0.0 OR rtt_vivo_lp > 0.0 OR (rtt_vivo_rbd > 0.0 AND rtt_vivo_rbd IS NOT NULL) THEN 1 ELSE 0 END),
                SUM(CASE WHEN rtt_micks_mm > 0.0 OR rtt_micks_lf > 0.0 OR rtt_micks_lp > 0.0 OR (rtt_micks_rbd > 0.0 AND rtt_micks_rbd IS NOT NULL) THEN 1 ELSE 0 END),
                SUM(CASE WHEN (rtt_vivo_mm > 0.0 AND rtt_vivo_mm <= 150.0) AND (rtt_vivo_rbd > 0.0 AND rtt_vivo_rbd <= 150.0) THEN 1 ELSE 0 END),
                SUM(CASE WHEN (rtt_micks_mm > 0.0 AND rtt_micks_mm <= 250.0) AND (rtt_micks_rbd > 0.0 AND rtt_micks_rbd <= 250.0) THEN 1 ELSE 0 END)
            FROM telemetry
            WHERE timestamp >= ?
        ''', (since_date,))
        row_up = cursor.fetchone()
        
        if row_up and row_up[0] > 0:
            total = row_up[0]
            v_up = (row_up[1] / total) * 100.0
            m_up = (row_up[2] / total) * 100.0
            v_sla = (row_up[3] / total) * 100.0
            m_sla = (row_up[4] / total) * 100.0
        else:
            v_up, m_up, v_sla, m_sla = 100.0, 100.0, 100.0, 100.0
            
        uptime_report[name] = {
            "vivo_uptime": round(v_up, 2),
            "micks_uptime": round(m_up, 2),
            "vivo_sla": round(v_sla, 2),
            "micks_sla": round(m_sla, 2)
        }
        
    conn.close()

    def make_stats_dict(row):
        if not row or row[0] is None:
            return {"vivo_rx": 0, "vivo_tx": 0, "micks_rx": 0, "micks_tx": 0}
        return {
            "vivo_rx": row[0],
            "vivo_tx": row[1],
            "micks_rx": row[2],
            "micks_tx": row[3]
        }

    rtt_peaks = {}
    if row_rtt_peaks:
        rtt_peaks = {
            "mm_vivo_max": row_rtt_peaks[0] or 0.0, "mm_vivo_min": row_rtt_peaks[1] or 0.0,
            "mm_micks_max": row_rtt_peaks[2] or 0.0, "mm_micks_min": row_rtt_peaks[3] or 0.0,
            "lf_vivo_max": row_rtt_peaks[4] or 0.0, "lf_vivo_min": row_rtt_peaks[5] or 0.0,
            "lf_micks_max": row_rtt_peaks[6] or 0.0, "lf_micks_min": row_rtt_peaks[7] or 0.0,
            "lp_vivo_max": row_rtt_peaks[8] or 0.0, "lp_vivo_min": row_rtt_peaks[9] or 0.0,
            "lp_micks_max": row_rtt_peaks[10] or 0.0, "lp_micks_min": row_rtt_peaks[11] or 0.0,
            "ld_vivo_max": row_rtt_peaks[12] or 0.0, "ld_vivo_min": row_rtt_peaks[13] or 0.0,
            "ld_micks_max": row_rtt_peaks[14] or 0.0, "ld_micks_min": row_rtt_peaks[15] or 0.0,
            "lda_vivo_max": row_rtt_peaks[16] or 0.0, "lda_vivo_min": row_rtt_peaks[17] or 0.0,
            "lda_micks_max": row_rtt_peaks[18] or 0.0, "lda_micks_min": row_rtt_peaks[19] or 0.0,
            "rbd_vivo_max": row_rtt_peaks[20] or 0.0, "rbd_vivo_min": row_rtt_peaks[21] or 0.0,
            "rbd_micks_max": row_rtt_peaks[22] or 0.0, "rbd_micks_min": row_rtt_peaks[23] or 0.0,
        }

    return {
        "today": make_stats_dict(row_today),
        "month": make_stats_dict(row_month),
        "peaks": make_stats_dict(row_peaks_24h),
        "peaks_table": {
            "vivo_rx": row_peaks_table[0] if (row_peaks_table and row_peaks_table[0] is not None) else 0.0,
            "vivo_tx": row_peaks_table[1] if (row_peaks_table and row_peaks_table[1] is not None) else 0.0,
            "micks_rx": row_peaks_table[2] if (row_peaks_table and row_peaks_table[2] is not None) else 0.0,
            "micks_tx": row_peaks_table[3] if (row_peaks_table and row_peaks_table[3] is not None) else 0.0,
            "vivo_rx_avg": row_peaks_table[4] if (row_peaks_table and row_peaks_table[4] is not None) else 0.0,
            "vivo_tx_avg": row_peaks_table[5] if (row_peaks_table and row_peaks_table[5] is not None) else 0.0,
            "micks_rx_avg": row_peaks_table[6] if (row_peaks_table and row_peaks_table[6] is not None) else 0.0,
            "micks_tx_avg": row_peaks_table[7] if (row_peaks_table and row_peaks_table[7] is not None) else 0.0
        },
        "rtt_peaks": rtt_peaks,
        "uptime_report": uptime_report
    }
