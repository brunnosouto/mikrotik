import os
import sqlite3
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'telemetry.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            link_ativo TEXT,
            rtt_vivo_mm REAL,
            rtt_vivo_lf REAL,
            rtt_vivo_lp REAL,
            rtt_micks_mm REAL,
            rtt_micks_lf REAL,
            rtt_micks_lp REAL,
            cpu INTEGER,
            temp INTEGER,
            ram INTEGER,
            uptime TEXT,
            traffic_vivo_rx REAL,
            traffic_vivo_tx REAL,
            traffic_micks_rx REAL,
            traffic_micks_tx REAL,
            traffic_lan_rx REAL,
            traffic_lan_tx REAL
        )
    ''')
    
    # Run automatic safe migrations for new columns
    cursor.execute("PRAGMA table_info(telemetry)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = {
        'dhcp_active_leases': 'INTEGER DEFAULT 0',
        'eth1_speed': 'TEXT DEFAULT "1Gbps"',
        'eth2_speed': 'TEXT DEFAULT "1Gbps"',
        'eth1_errors': 'INTEGER DEFAULT 0',
        'eth2_errors': 'INTEGER DEFAULT 0',
        'logs': 'TEXT DEFAULT ""',
        'rtt_vivo_laudite': 'REAL DEFAULT 0.0',
        'rtt_micks_laudite': 'REAL DEFAULT 0.0',
        'rtt_vivo_laudite_asr': 'REAL DEFAULT 0.0',
        'rtt_micks_laudite_asr': 'REAL DEFAULT 0.0',
        'rtt_vivo_rbd': 'REAL DEFAULT 0.0',
        'rtt_micks_rbd': 'REAL DEFAULT 0.0'
    }
    for col, col_type in new_cols.items():
        if col not in columns:
            cursor.execute(f"ALTER TABLE telemetry ADD COLUMN {col} {col_type}")
            
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic_accumulation (
            date TEXT PRIMARY KEY,
            vivo_rx INTEGER DEFAULT 0,
            vivo_tx INTEGER DEFAULT 0,
            micks_rx INTEGER DEFAULT 0,
            micks_tx INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic_metadata (
            key TEXT PRIMARY KEY,
            val TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic_peaks_log (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            vivo_rx REAL DEFAULT 0.0,
            vivo_tx REAL DEFAULT 0.0,
            micks_rx REAL DEFAULT 0.0,
            micks_tx REAL DEFAULT 0.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS network_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            src_ip TEXT,
            hostname TEXT,
            domain TEXT,
            hits INTEGER DEFAULT 1
        )
    ''')

    # Reset command removed to preserve history across restarts
    conn.commit()
    conn.close()

init_db()
def parse_rtt(rtt_str):
    if not rtt_str:
        return 0.0
    rtt_str = str(rtt_str).strip()
    if ':' not in rtt_str:
        try:
            return float(rtt_str)
        except:
            return 0.0
    try:
        parts = rtt_str.split(':')
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000.0
        return round(total_ms, 1)
    except Exception:
        return 0.0

def parse_float(val):
    if val is None or str(val).strip() == "":
        return 0.0
    try:
        return float(val)
    except:
        return 0.0

def parse_int(val):
    if val is None or str(val).strip() == "":
        return 0
    try:
        return int(val)
    except:
        return 0

import datetime

# Memory storage for the latest 5-second traffic rates to feed the real-time UI
latest_traffic = {
    'traffic_vivo_rx': 0.0,
    'traffic_vivo_tx': 0.0,
    'traffic_micks_rx': 0.0,
    'traffic_micks_tx': 0.0,
    'traffic_lan_rx': 0.0,
    'traffic_lan_tx': 0.0,
    'timestamp': None
}

import time
current_minute_peaks = {
    'vivo_rx': 0.0,
    'vivo_tx': 0.0,
    'micks_rx': 0.0,
    'micks_tx': 0.0
}
last_peak_write_time = time.time()

@app.route('/api/traffic', methods=['POST'])
def receive_traffic():
    try:
        data = request.get_json(silent=True) or request.form
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # 1. Update in-memory real-time rates
        global latest_traffic, current_minute_peaks, last_peak_write_time
        vivo_rx = parse_float(data.get('traffic_vivo_rx', 0))
        vivo_tx = parse_float(data.get('traffic_vivo_tx', 0))
        micks_rx = parse_float(data.get('traffic_micks_rx', 0))
        micks_tx = parse_float(data.get('traffic_micks_tx', 0))

        latest_traffic['traffic_vivo_rx'] = vivo_rx
        latest_traffic['traffic_vivo_tx'] = vivo_tx
        latest_traffic['traffic_micks_rx'] = micks_rx
        latest_traffic['traffic_micks_tx'] = micks_tx
        latest_traffic['traffic_lan_rx'] = parse_float(data.get('traffic_lan_rx', 0))
        latest_traffic['traffic_lan_tx'] = parse_float(data.get('traffic_lan_tx', 0))
        latest_traffic['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update peak rates for the current minute
        current_minute_peaks['vivo_rx'] = max(current_minute_peaks['vivo_rx'], vivo_rx)
        current_minute_peaks['vivo_tx'] = max(current_minute_peaks['vivo_tx'], vivo_tx)
        current_minute_peaks['micks_rx'] = max(current_minute_peaks['micks_rx'], micks_rx)
        current_minute_peaks['micks_tx'] = max(current_minute_peaks['micks_tx'], micks_tx)

        # Write peak logs to SQLite every 60s and clear old data (> 24 hours)
        now_time = time.time()
        if (now_time - last_peak_write_time) >= 60.0:
            try:
                conn_peak = sqlite3.connect(DB_PATH)
                cursor_peak = conn_peak.cursor()
                cursor_peak.execute('''
                    INSERT INTO traffic_peaks_log (vivo_rx, vivo_tx, micks_rx, micks_tx)
                    VALUES (?, ?, ?, ?)
                ''', (
                    current_minute_peaks['vivo_rx'],
                    current_minute_peaks['vivo_tx'],
                    current_minute_peaks['micks_rx'],
                    current_minute_peaks['micks_tx']
                ))
                cursor_peak.execute("DELETE FROM traffic_peaks_log WHERE timestamp < datetime('now', '-30 days')")
                conn_peak.commit()
                conn_peak.close()
            except Exception as e_db:
                print("Error writing to peak log database:", e_db)

            # Reset current minute buffers
            current_minute_peaks = {
                'vivo_rx': 0.0,
                'vivo_tx': 0.0,
                'micks_rx': 0.0,
                'micks_tx': 0.0
            }
            last_peak_write_time = now_time

        # 2. Extract byte counters to calculate accumulated traffic
        bytes_keys = ['bytes_vivo_rx', 'bytes_vivo_tx', 'bytes_micks_rx', 'bytes_micks_tx']
        current_bytes = {}
        for key in bytes_keys:
            current_bytes[key] = parse_int(data.get(key, 0))

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Load last byte counters from metadata
        cursor.execute("SELECT key, val FROM traffic_metadata")
        metadata = dict(cursor.fetchall())

        deltas = {}
        for key in bytes_keys:
            current_val = current_bytes[key]
            last_val = parse_int(metadata.get(key, None))
            
            if last_val is None:
                # First telemetry payload or no previous record, delta is 0
                deltas[key] = 0
            elif current_val >= last_val:
                diff = current_val - last_val
                # If delta is abnormally large (e.g. > 500 MB), treat as baseline reset
                if diff > 500 * 1024 * 1024:
                    deltas[key] = 0
                else:
                    deltas[key] = diff
            else:
                # Router rebooted / counters reset
                if current_val > 500 * 1024 * 1024:
                    deltas[key] = 0
                else:
                    deltas[key] = current_val
            
            # Save new value to metadata
            cursor.execute('''
                INSERT OR REPLACE INTO traffic_metadata (key, val) VALUES (?, ?)
            ''', (key, str(current_val)))

        # 3. Accumulate deltas for today's date
        tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
        today = datetime.datetime.now(tz_gmt3).date().isoformat()
        cursor.execute('''
            INSERT OR IGNORE INTO traffic_accumulation (date, vivo_rx, vivo_tx, micks_rx, micks_tx)
            VALUES (?, 0, 0, 0, 0)
        ''', (today,))

        cursor.execute('''
            UPDATE traffic_accumulation
            SET vivo_rx = vivo_rx + ?,
                vivo_tx = vivo_tx + ?,
                micks_rx = micks_rx + ?,
                micks_tx = micks_tx + ?
            WHERE date = ?
        ''', (
            deltas['bytes_vivo_rx'],
            deltas['bytes_vivo_tx'],
            deltas['bytes_micks_rx'],
            deltas['bytes_micks_tx'],
            today
        ))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Traffic rates and counters updated"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    try:
        data = request.get_json(silent=True) or request.form
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        import datetime
        tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
        now_gmt3 = datetime.datetime.now(tz_gmt3)
        timestamp_str = now_gmt3.strftime('%Y-%m-%d %H:%M:%S')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO telemetry (
                timestamp, link_ativo, rtt_vivo_mm, rtt_vivo_lf, rtt_vivo_lp,
                rtt_micks_mm, rtt_micks_lf, rtt_micks_lp,
                cpu, temp, ram, uptime,
                traffic_vivo_rx, traffic_vivo_tx,
                traffic_micks_rx, traffic_micks_tx,
                traffic_lan_rx, traffic_lan_tx,
                dhcp_active_leases, eth1_speed, eth2_speed,
                eth1_errors, eth2_errors, logs,
                rtt_vivo_laudite, rtt_micks_laudite,
                rtt_vivo_laudite_asr, rtt_micks_laudite_asr,
                rtt_vivo_rbd, rtt_micks_rbd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp_str,
            data.get('link_ativo', 'VIVO'),
            parse_rtt(data.get('rtt_vivo_mm', data.get('MONITOR_VIVO_MOBILEMED', 0))),
            parse_rtt(data.get('rtt_vivo_lf', data.get('MONITOR_VIVO_LIFEFOCUS', 0))),
            parse_rtt(data.get('rtt_vivo_lp', data.get('MONITOR_VIVO_LIFEPLUS', 0))),
            parse_rtt(data.get('rtt_micks_mm', data.get('MONITOR_MICKS_MOBILEMED', 0))),
            parse_rtt(data.get('rtt_micks_lf', data.get('MONITOR_MICKS_LIFEFOCUS', 0))),
            parse_rtt(data.get('rtt_micks_lp', data.get('MONITOR_MICKS_LIFEPLUS', 0))),
            parse_int(data.get('cpu', 0)),
            parse_int(data.get('temp', 0)),
            parse_int(data.get('ram', 0)),
            data.get('uptime', '00:00:00'),
            parse_float(data.get('traffic_vivo_rx', 0)),
            parse_float(data.get('traffic_vivo_tx', 0)),
            parse_float(data.get('traffic_micks_rx', 0)),
            parse_float(data.get('traffic_micks_tx', 0)),
            parse_float(data.get('traffic_lan_rx', 0)),
            parse_float(data.get('traffic_lan_tx', 0)),
            parse_int(data.get('dhcp_active_leases', 0)),
            data.get('eth1_speed', '1Gbps'),
            data.get('eth2_speed', '1Gbps'),
            parse_int(data.get('eth1_errors', 0)),
            parse_int(data.get('eth2_errors', 0)),
            data.get('logs', ''),
            parse_rtt(data.get('rtt_vivo_laudite', data.get('MONITOR_VIVO_LAUDITE', 0))),
            parse_rtt(data.get('rtt_micks_laudite', data.get('MONITOR_MICKS_LAUDITE', 0))),
            parse_rtt(data.get('rtt_vivo_laudite_asr', data.get('MONITOR_VIVO_LAUDITE_ASR', 0))),
            parse_rtt(data.get('rtt_micks_laudite_asr', data.get('MONITOR_MICKS_LAUDITE_ASR', 0))),
            parse_rtt(data.get('rtt_vivo_rbd', data.get('MONITOR_VIVO_RBD', 0))),
            parse_rtt(data.get('rtt_micks_rbd', data.get('MONITOR_MICKS_RBD', 0)))
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Telemetry received"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    hours = request.args.get('hours', 1.0, type=float)
    
    import datetime
    tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
    now_local = datetime.datetime.now(tz_gmt3)
    time_limit = now_local - datetime.timedelta(hours=hours)
    time_limit_str = time_limit.strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM telemetry WHERE timestamp >= ? ORDER BY id ASC', (time_limit_str,))
    rows = cursor.fetchall()
    conn.close()
    
    raw_result = [dict(row) for row in rows]
    
    # Determine downsampling interval based on the range (hours) requested
    interval_minutes = 1
    if hours > 1.5 and hours <= 12:
        interval_minutes = 5
    elif hours > 12 and hours <= 24:
        interval_minutes = 10
    elif hours > 24 and hours <= 168:
        interval_minutes = 60
    elif hours > 168:
        interval_minutes = 120
        
    result = raw_result
    if interval_minutes > 1 and len(raw_result) > 100:
        grouped = {}
        for item in raw_result:
            try:
                dt = datetime.datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S')
                bucket_minute = (dt.minute // interval_minutes) * interval_minutes
                bucket_time = dt.replace(minute=bucket_minute, second=0, microsecond=0)
                bucket_key = bucket_time.strftime('%Y-%m-%d %H:%M')
                
                if bucket_key not in grouped:
                    grouped[bucket_key] = []
                grouped[bucket_key].append(item)
            except Exception:
                continue
                
        result = []
        for bucket_key in sorted(grouped.keys()):
            items = grouped[bucket_key]
            representative = {}
            for key in items[0].keys():
                if key == 'id':
                    representative[key] = items[0][key]
                elif key == 'timestamp':
                    representative[key] = bucket_key + ":00"
                elif key == 'link_ativo':
                    links = [x['link_ativo'] for x in items]
                    representative[key] = max(set(links), key=links.count)
                elif key in ['uptime', 'eth1_speed', 'eth2_speed', 'logs']:
                    representative[key] = items[-1][key]
                else:
                    vals = [x[key] for x in items if x[key] is not None]
                    if vals:
                        representative[key] = round(sum(vals) / len(vals), 1)
                    else:
                        representative[key] = 0.0
            result.append(representative)
            
    # Override the latest element's traffic rates with the in-memory 5-second real-time values if available
    if result and latest_traffic['timestamp'] is not None:
        result[-1]['traffic_vivo_rx'] = latest_traffic['traffic_vivo_rx']
        result[-1]['traffic_vivo_tx'] = latest_traffic['traffic_vivo_tx']
        result[-1]['traffic_micks_rx'] = latest_traffic['traffic_micks_rx']
        result[-1]['traffic_micks_tx'] = latest_traffic['traffic_micks_tx']
        result[-1]['traffic_lan_rx'] = latest_traffic['traffic_lan_rx']
        result[-1]['traffic_lan_tx'] = latest_traffic['traffic_lan_tx']
        
    return jsonify(result)

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    days = request.args.get('days', 7, type=int)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Fetch records for the last N days ordered by ID ascending
    cursor.execute('''
        SELECT * FROM telemetry 
        WHERE timestamp >= datetime('now', ?) 
        ORDER BY id ASC
    ''', (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()

    incidents = []
    if not rows:
        return jsonify(incidents)

    prev_link = rows[0]['link_ativo']
    micks_start_time = None
    
    # We will track active state for each destination to group events
    # States: 'OK', 'HIGH_LATENCY', 'OFFLINE'
    dest_states = {
        'VIVO_MM': 'OK', 'VIVO_LF': 'OK', 'VIVO_LP': 'OK', 'VIVO_RBD': 'OK',
        'MICKS_MM': 'OK', 'MICKS_LF': 'OK', 'MICKS_LP': 'OK', 'MICKS_RBD': 'OK',
        'VIVO_LAUDITE': 'OK', 'MICKS_LAUDITE': 'OK'
    }

    def check_dest_state(rtt, limit):
        if rtt is None:
            return 'OFFLINE'
        try:
            rtt_val = float(rtt)
        except:
            return 'OFFLINE'
        if rtt_val == 0.0:
            return 'OFFLINE'
        elif rtt_val > limit:
            return 'HIGH_LATENCY'
        return 'OK'

    limits = {
        'MM': 150.0,
        'LF': 280.0,
        'LP': 280.0,
        'RBD': 150.0
    }

    for row_raw in rows:
        row = dict(row_raw)
        timestamp = row['timestamp']
        current_link = row['link_ativo']

        # 1. Detect link switch
        if current_link != prev_link:
            severity = "warning"
            if current_link == "MICKS":
                # VIVO to MICKS switch
                micks_start_time = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                reasons = []
                r_mm = parse_float(row['rtt_vivo_mm'])
                r_lf = parse_float(row['rtt_vivo_lf'])
                r_lp = parse_float(row['rtt_vivo_lp'])
                r_rbd = parse_float(row.get('rtt_vivo_rbd', 0.0))
                
                if r_mm == 0.0 or r_mm > limits['MM']:
                    status = "OFFLINE" if r_mm == 0.0 else f"RTT {r_mm}ms (Limite {limits['MM']}ms)"
                    reasons.append(f"MobileMed {status}")
                if r_lf == 0.0 or r_lf > limits['LF']:
                    status = "OFFLINE" if r_lf == 0.0 else f"RTT {r_lf}ms (Limite {limits['LF']}ms)"
                    reasons.append(f"LifeFocus {status}")
                if r_lp == 0.0 or r_lp > limits['LP']:
                    status = "OFFLINE" if r_lp == 0.0 else f"RTT {r_lp}ms (Limite {limits['LP']}ms)"
                    reasons.append(f"LifePlus {status}")
                if r_rbd == 0.0 or r_rbd > limits['RBD']:
                    status = "OFFLINE" if r_rbd == 0.0 else f"RTT {r_rbd}ms (Limite {limits['RBD']}ms)"
                    reasons.append(f"RBD PACS {status}")
                
                reason_str = ", ".join(reasons) if reasons else "Mudança preventiva ou manual"
                msg = f"⚠️ ROTA ALTERADA: VIVO -> MICKS. Motivo: Instabilidade em {reason_str}"
                severity = "danger"
            else:
                # MICKS to VIVO switch
                duration_str = ""
                if micks_start_time:
                    try:
                        v_back = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        diff_sec = int((v_back - micks_start_time).total_seconds())
                        if diff_sec >= 60:
                            duration_str = f" (Duração: {diff_sec // 60}m {diff_sec % 60}s)"
                        else:
                            duration_str = f" (Duração: {diff_sec}s)"
                    except Exception:
                        pass
                    micks_start_time = None
                
                reasons = []
                r_mm = parse_float(row['rtt_vivo_mm'])
                r_lf = parse_float(row['rtt_vivo_lf'])
                r_lp = parse_float(row['rtt_vivo_lp'])
                r_rbd = parse_float(row.get('rtt_vivo_rbd', 0.0))
                
                if r_mm > 0.0 and r_mm <= limits['MM']:
                    reasons.append(f"MobileMed {r_mm}ms")
                if r_lf > 0.0 and r_lf <= limits['LF']:
                    reasons.append(f"LifeFocus {r_lf}ms")
                if r_lp > 0.0 and r_lp <= limits['LP']:
                    reasons.append(f"LifePlus {r_lp}ms")
                if r_rbd > 0.0 and r_rbd <= limits['RBD']:
                    reasons.append(f"RBD PACS {r_rbd}ms")
                
                reason_str = ", ".join(reasons) if reasons else "Restabelecimento de SLA"
                msg = f"✅ RETORNO: VIVO restabelecida. Motivo: Normalização de {reason_str}{duration_str}"
                severity = "success"

            incidents.append({
                "timestamp": timestamp,
                "type": "SWITCH",
                "severity": severity,
                "message": msg
            })
            prev_link = current_link

        # 2. Detect SLA breaches / offline status
        checks = [
            ('VIVO_MM', row['rtt_vivo_mm'], limits['MM'], "VIVO - MobileMed"),
            ('VIVO_LF', row['rtt_vivo_lf'], limits['LF'], "VIVO - LifeFocus"),
            ('VIVO_LP', row['rtt_vivo_lp'], limits['LP'], "VIVO - LifePlus"),
            ('VIVO_RBD', row.get('rtt_vivo_rbd', 0.0), limits['RBD'], "VIVO - RBD PACS"),
            ('MICKS_MM', row['rtt_micks_mm'], limits['MM'], "MICKS - MobileMed"),
            ('MICKS_LF', row['rtt_micks_lf'], limits['LF'], "MICKS - LifeFocus"),
            ('MICKS_LP', row['rtt_micks_lp'], limits['LP'], "MICKS - LifePlus"),
            ('MICKS_RBD', row.get('rtt_micks_rbd', 0.0), limits['RBD'], "MICKS - RBD PACS"),
            ('VIVO_LAUDITE', row['rtt_vivo_laudite'], 250.0, "VIVO - Laudite"),
            ('MICKS_LAUDITE', row['rtt_micks_laudite'], 250.0, "MICKS - Laudite"),
        ]

        for key, rtt, limit, display_name in checks:
            new_state = check_dest_state(rtt, limit)
            old_state = dest_states[key]

            if new_state != old_state:
                if new_state == 'OFFLINE':
                    incidents.append({
                        "timestamp": timestamp,
                        "type": "OFFLINE",
                        "severity": "danger",
                        "message": f"{display_name} ficou OFFLINE (Sem resposta do Netwatch)"
                    })
                elif new_state == 'HIGH_LATENCY':
                    incidents.append({
                        "timestamp": timestamp,
                        "type": "SLA_BREACH",
                        "severity": "warning",
                        "message": f"{display_name} RTT elevado: {rtt} ms (Limite: {limit} ms)"
                    })
                elif new_state == 'OK':
                    incidents.append({
                        "timestamp": timestamp,
                        "type": "RECOVERY",
                        "severity": "success",
                        "message": f"{display_name} normalizado"
                    })
                dest_states[key] = new_state

    # Return in reverse chronological order
    incidents.reverse()
    return jsonify(incidents)

@app.route('/api/traffic/stats', methods=['GET'])
def get_traffic_stats():
    try:
        peak_days = request.args.get('peak_days', 30, type=int)
        tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
        today = datetime.datetime.now(tz_gmt3).date().isoformat()
        current_month_prefix = today[:7] + '%' # e.g. '2026-06%'
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Fetch today's stats
        cursor.execute('''
            SELECT SUM(vivo_rx), SUM(vivo_tx), SUM(micks_rx), SUM(micks_tx)
            FROM traffic_accumulation WHERE date = ?
        ''', (today,))
        row_today = cursor.fetchone()
        
        # 2. Fetch monthly stats
        cursor.execute('''
            SELECT SUM(vivo_rx), SUM(vivo_tx), SUM(micks_rx), SUM(micks_tx)
            FROM traffic_accumulation WHERE date LIKE ?
        ''', (current_month_prefix,))
        row_month = cursor.fetchone()

        # 3. Fetch peak rates of the last 24 hours (for charts)
        cursor.execute('''
            SELECT MAX(vivo_rx), MAX(vivo_tx), MAX(micks_rx), MAX(micks_tx)
            FROM traffic_peaks_log
            WHERE timestamp >= datetime('now', '-24 hours')
        ''')
        row_peaks_24h = cursor.fetchone()

        # 3b. Fetch peak rates of the chosen interval (7 or 30 days) for the table
        cursor.execute('''
            SELECT MAX(vivo_rx), MAX(vivo_tx), MAX(micks_rx), MAX(micks_tx),
                   AVG(vivo_rx), AVG(vivo_tx), AVG(micks_rx), AVG(micks_tx)
            FROM traffic_peaks_log
            WHERE timestamp >= datetime('now', ?)
        ''', (f'-{peak_days} days',))
        row_peaks_table = cursor.fetchone()

        # 4. Fetch RTT high/low peaks of the last 24 hours
        # For MIN, we exclude 0.0 values so that offline periods don't show as a 0ms peak.
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

        # Query values from database - 24h
        db_vivo_rx_24h = row_peaks_24h[0] if (row_peaks_24h and row_peaks_24h[0] is not None) else 0.0
        db_vivo_tx_24h = row_peaks_24h[1] if (row_peaks_24h and row_peaks_24h[1] is not None) else 0.0
        db_micks_rx_24h = row_peaks_24h[2] if (row_peaks_24h and row_peaks_24h[2] is not None) else 0.0
        db_micks_tx_24h = row_peaks_24h[3] if (row_peaks_24h and row_peaks_24h[3] is not None) else 0.0

        # Query values from database - chosen table period
        db_vivo_rx_table = row_peaks_table[0] if (row_peaks_table and row_peaks_table[0] is not None) else 0.0
        db_vivo_tx_table = row_peaks_table[1] if (row_peaks_table and row_peaks_table[1] is not None) else 0.0
        db_micks_rx_table = row_peaks_table[2] if (row_peaks_table and row_peaks_table[2] is not None) else 0.0
        db_micks_tx_table = row_peaks_table[3] if (row_peaks_table and row_peaks_table[3] is not None) else 0.0

        db_vivo_rx_avg = row_peaks_table[4] if (row_peaks_table and row_peaks_table[4] is not None) else 0.0
        db_vivo_tx_avg = row_peaks_table[5] if (row_peaks_table and row_peaks_table[5] is not None) else 0.0
        db_micks_rx_avg = row_peaks_table[6] if (row_peaks_table and row_peaks_table[6] is not None) else 0.0
        db_micks_tx_avg = row_peaks_table[7] if (row_peaks_table and row_peaks_table[7] is not None) else 0.0

        # Combine with current minute's peak for absolute realtime peak precision
        peak_vivo_rx_24h = max(db_vivo_rx_24h, current_minute_peaks['vivo_rx'])
        peak_vivo_tx_24h = max(db_vivo_tx_24h, current_minute_peaks['vivo_tx'])
        peak_micks_rx_24h = max(db_micks_rx_24h, current_minute_peaks['micks_rx'])
        peak_micks_tx_24h = max(db_micks_tx_24h, current_minute_peaks['micks_tx'])

        peak_vivo_rx_table = max(db_vivo_rx_table, current_minute_peaks['vivo_rx'])
        peak_vivo_tx_table = max(db_vivo_tx_table, current_minute_peaks['vivo_tx'])
        peak_micks_rx_table = max(db_micks_rx_table, current_minute_peaks['micks_rx'])
        peak_micks_tx_table = max(db_micks_tx_table, current_minute_peaks['micks_tx'])

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
                "rbd_micks_max": row_rtt_peaks[22] or 0.0, "rbd_micks_min": row_rtt_peaks[23] or 0.0
            }
        else:
            rtt_peaks = {
                "mm_vivo_max": 0.0, "mm_vivo_min": 0.0, "mm_micks_max": 0.0, "mm_micks_min": 0.0,
                "lf_vivo_max": 0.0, "lf_vivo_min": 0.0, "lf_micks_max": 0.0, "lf_micks_min": 0.0,
                "lp_vivo_max": 0.0, "lp_vivo_min": 0.0, "lp_micks_max": 0.0, "lp_micks_min": 0.0,
                "ld_vivo_max": 0.0, "ld_vivo_min": 0.0, "ld_micks_max": 0.0, "ld_micks_min": 0.0,
                "lda_vivo_max": 0.0, "lda_vivo_min": 0.0, "lda_micks_max": 0.0, "lda_micks_min": 0.0,
                "rbd_vivo_max": 0.0, "rbd_vivo_min": 0.0, "rbd_micks_max": 0.0, "rbd_micks_min": 0.0
            }

        return jsonify({
            "today": make_stats_dict(row_today),
            "month": make_stats_dict(row_month),
            "peaks": {
                "vivo_rx": peak_vivo_rx_24h,
                "vivo_tx": peak_vivo_tx_24h,
                "micks_rx": peak_micks_rx_24h,
                "micks_tx": peak_micks_tx_24h
            },
            "peaks_table": {
                "vivo_rx": peak_vivo_rx_table,
                "vivo_tx": peak_vivo_tx_table,
                "micks_rx": peak_micks_rx_table,
                "micks_tx": peak_micks_tx_table,
                "vivo_rx_avg": db_vivo_rx_avg,
                "vivo_tx_avg": db_vivo_tx_avg,
                "micks_rx_avg": db_micks_rx_avg,
                "micks_tx_avg": db_micks_tx_avg
            },
            "rtt_peaks": rtt_peaks
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/network-activity', methods=['POST'])
def receive_network_activity():
    try:
        data = request.get_json(silent=True) or request.form
        if not data or 'connections' not in data:
            return jsonify({"status": "error", "message": "Missing connections payload"}), 400

        connections = data.get('connections', [])
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get current GMT-3 timestamp
        tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
        now_str = datetime.datetime.now(tz_gmt3).strftime('%Y-%m-%d %H:%M:%S')

        for item in connections:
            src_ip = item.get('src_ip', '').strip()
            domain = item.get('domain', '').strip()
            hostname = item.get('hostname', '').strip()

            if not src_ip or not domain:
                continue

            # Update if already exists in active connection database within the last 5 minutes, else insert
            cursor.execute('''
                SELECT id, hits FROM network_activity 
                WHERE src_ip = ? AND domain = ? AND timestamp >= datetime('now', '-5 minutes')
            ''', (src_ip, domain))
            row = cursor.fetchone()

            if row:
                conn_id, hits = row
                cursor.execute('''
                    UPDATE network_activity 
                    SET hits = ?, timestamp = ?, hostname = ?
                    WHERE id = ?
                ''', (hits + 1, now_str, hostname or src_ip, conn_id))
            else:
                cursor.execute('''
                    INSERT INTO network_activity (timestamp, src_ip, hostname, domain, hits)
                    VALUES (?, ?, ?, ?, 1)
                ''', (now_str, src_ip, hostname or src_ip, domain))

        # Clean old records older than 5 minutes
        cursor.execute("DELETE FROM network_activity WHERE timestamp < datetime('now', '-5 minutes')")
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Network activity updated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/network-activity', methods=['GET'])
def get_network_activity():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Clean obsolete entries on retrieve just in case
        cursor.execute("DELETE FROM network_activity WHERE timestamp < datetime('now', '-5 minutes')")
        conn.commit()

        # Group connections to show top active devices and destinations
        cursor.execute('''
            SELECT src_ip, hostname, domain, SUM(hits) as total_hits, MAX(timestamp) as last_seen
            FROM network_activity
            GROUP BY src_ip, domain
            ORDER BY last_seen DESC, total_hits DESC
            LIMIT 30
        ''')
        rows = cursor.fetchall()
        conn.close()

        activity = []
        for r in rows:
            activity.append({
                "src_ip": r[0],
                "hostname": r[1],
                "domain": r[2],
                "hits": r[3],
                "last_seen": r[4]
            })

        return jsonify(activity)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
