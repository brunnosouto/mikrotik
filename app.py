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
                traffic_lan_rx, traffic_lan_tx
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            parse_float(data.get('traffic_lan_tx', 0))
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

@app.route('/')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
