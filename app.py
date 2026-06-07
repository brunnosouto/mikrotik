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
        'logs': 'TEXT DEFAULT ""'
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

    # Reset traffic stats and metadata to clear historical fake terabytes
    cursor.execute("DELETE FROM traffic_metadata")
    cursor.execute("DELETE FROM traffic_accumulation")
    cursor.execute("DELETE FROM traffic_peaks_log")

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
                cursor_peak.execute("DELETE FROM traffic_peaks_log WHERE timestamp < datetime('now', '-24 hours')")
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
        today = datetime.date.today().isoformat()
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

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO telemetry (
                link_ativo, rtt_vivo_mm, rtt_vivo_lf, rtt_vivo_lp,
                rtt_micks_mm, rtt_micks_lf, rtt_micks_lp,
                cpu, temp, ram, uptime,
                traffic_vivo_rx, traffic_vivo_tx,
                traffic_micks_rx, traffic_micks_tx,
                traffic_lan_rx, traffic_lan_tx,
                dhcp_active_leases, eth1_speed, eth2_speed,
                eth1_errors, eth2_errors, logs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
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
            data.get('logs', '')
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
    limit = request.args.get('limit', 50, type=int)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM telemetry ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in reversed(rows):
        result.append(dict(row))
        
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
    days = request.args.get('days', 3, type=int)
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
    
    # We will track active state for each destination to group events
    # States: 'OK', 'HIGH_LATENCY', 'OFFLINE'
    dest_states = {
        'VIVO_MM': 'OK', 'VIVO_LF': 'OK', 'VIVO_LP': 'OK',
        'MICKS_MM': 'OK', 'MICKS_LF': 'OK', 'MICKS_LP': 'OK'
    }

    def check_dest_state(rtt, limit):
        if rtt == 0.0:
            return 'OFFLINE'
        elif rtt > limit:
            return 'HIGH_LATENCY'
        return 'OK'

    limits = {
        'MM': 150.0,
        'LF': 280.0,
        'LP': 280.0
    }

    for row in rows:
        timestamp = row['timestamp']
        current_link = row['link_ativo']

        # 1. Detect link switch
        if current_link != prev_link:
            incidents.append({
                "timestamp": timestamp,
                "type": "SWITCH",
                "severity": "warning",
                "message": f"Link ativo alterado de {prev_link} para {current_link}"
            })
            prev_link = current_link

        # 2. Detect SLA breaches / offline status
        checks = [
            ('VIVO_MM', row['rtt_vivo_mm'], limits['MM'], "VIVO - MobileMed"),
            ('VIVO_LF', row['rtt_vivo_lf'], limits['LF'], "VIVO - LifeFocus"),
            ('VIVO_LP', row['rtt_vivo_lp'], limits['LP'], "VIVO - LifePlus"),
            ('MICKS_MM', row['rtt_micks_mm'], limits['MM'], "MICKS - MobileMed"),
            ('MICKS_LF', row['rtt_micks_lf'], limits['LF'], "MICKS - LifeFocus"),
            ('MICKS_LP', row['rtt_micks_lp'], limits['LP'], "MICKS - LifePlus"),
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
        today = datetime.date.today().isoformat()
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

        # 3. Fetch peak rates of the last 24 hours
        cursor.execute('''
            SELECT MAX(vivo_rx), MAX(vivo_tx), MAX(micks_rx), MAX(micks_tx)
            FROM traffic_peaks_log
            WHERE timestamp >= datetime('now', '-24 hours')
        ''')
        row_peaks = cursor.fetchone()

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

        # Query values from database
        db_vivo_rx = row_peaks[0] if (row_peaks and row_peaks[0] is not None) else 0.0
        db_vivo_tx = row_peaks[1] if (row_peaks and row_peaks[1] is not None) else 0.0
        db_micks_rx = row_peaks[2] if (row_peaks and row_peaks[2] is not None) else 0.0
        db_micks_tx = row_peaks[3] if (row_peaks and row_peaks[3] is not None) else 0.0

        # Combine with current minute's peak for absolute realtime peak precision
        peak_vivo_rx = max(db_vivo_rx, current_minute_peaks['vivo_rx'])
        peak_vivo_tx = max(db_vivo_tx, current_minute_peaks['vivo_tx'])
        peak_micks_rx = max(db_micks_rx, current_minute_peaks['micks_rx'])
        peak_micks_tx = max(db_micks_tx, current_minute_peaks['micks_tx'])

        return jsonify({
            "today": make_stats_dict(row_today),
            "month": make_stats_dict(row_month),
            "peaks": {
                "vivo_rx": peak_vivo_rx,
                "vivo_tx": peak_vivo_tx,
                "micks_rx": peak_micks_rx,
                "micks_tx": peak_micks_tx
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
