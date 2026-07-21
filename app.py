import os
import time
import sqlite3
import datetime
import subprocess
from flask import Flask, request, jsonify, render_template

# Auto-sync latest code from git on app initialization
try:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(app_dir, '.git')):
        subprocess.run(["git", "pull", "origin", "main"], cwd=app_dir, capture_output=True, timeout=10)
except Exception as e:
    pass

from db import init_db, get_db_connection, save_telemetry_record, prune_old_telemetry
from services.sla_service import calculate_traffic_stats, get_radiology_health_summary

app = Flask(__name__)

# Security Configuration
TELEMETRY_SECRET_TOKEN = os.environ.get('TELEMETRY_SECRET_TOKEN', 'mikrotik_secret_telemetry_token_2026')
START_TIME = time.time()

# In-memory traffic rate cache
latest_traffic = {
    'timestamp': None,
    'traffic_vivo_rx': 0,
    'traffic_vivo_tx': 0,
    'traffic_micks_rx': 0,
    'traffic_micks_tx': 0,
    'traffic_lan_rx': 0,
    'traffic_lan_tx': 0
}

# 1. Initialize Database and Prune Old Telemetry (>90 days)
init_db()
prune_old_telemetry(90)

# 2. Security Headers Middleware
@app.after_request
def apply_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# 3. Observability Health Check Endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM telemetry')
        total_records = cursor.fetchone()[0]
        conn.close()
        
        uptime_seconds = int(time.time() - START_TIME)
        return jsonify({
            "status": "healthy",
            "uptime_seconds": uptime_seconds,
            "database_status": "connected",
            "total_telemetry_records": total_records,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

# 4. Protected Telemetry Ingestion Endpoints
def is_authenticated(req):
    token = req.args.get('token') or req.headers.get('X-Telemetry-Token')
    if not token and req.is_json:
        token = req.json.get('token')
    return token == TELEMETRY_SECRET_TOKEN

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    if not is_authenticated(request):
        return jsonify({"status": "error", "message": "Unauthorized: Invalid or missing telemetry token"}), 401
    
    try:
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
            if not data:
                data = request.args.to_dict()
                
        save_telemetry_record(data)
        
        # Update in-memory real-time traffic rates
        latest_traffic['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        latest_traffic['traffic_vivo_rx'] = data.get('traffic_vivo_rx', 0)
        latest_traffic['traffic_vivo_tx'] = data.get('traffic_vivo_tx', 0)
        latest_traffic['traffic_micks_rx'] = data.get('traffic_micks_rx', 0)
        latest_traffic['traffic_micks_tx'] = data.get('traffic_micks_tx', 0)
        latest_traffic['traffic_lan_rx'] = data.get('traffic_lan_rx', 0)
        latest_traffic['traffic_lan_tx'] = data.get('traffic_lan_tx', 0)
        
        return jsonify({"status": "success", "message": "Telemetry received successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/traffic', methods=['POST'])
def receive_traffic():
    if not is_authenticated(request):
        return jsonify({"status": "error", "message": "Unauthorized: Invalid or missing telemetry token"}), 401
    
    try:
        data = request.json if request.is_json else request.form.to_dict()
        latest_traffic['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        latest_traffic['traffic_vivo_rx'] = data.get('traffic_vivo_rx', 0)
        latest_traffic['traffic_vivo_tx'] = data.get('traffic_vivo_tx', 0)
        latest_traffic['traffic_micks_rx'] = data.get('traffic_micks_rx', 0)
        latest_traffic['traffic_micks_tx'] = data.get('traffic_micks_tx', 0)
        latest_traffic['traffic_lan_rx'] = data.get('traffic_lan_rx', 0)
        latest_traffic['traffic_lan_tx'] = data.get('traffic_lan_tx', 0)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 5. Dashboard Data APIs
@app.route('/api/data', methods=['GET'])
def get_data():
    hours = request.args.get('hours', 1, type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM telemetry 
        WHERE timestamp >= datetime('now', ? || ' hours')
        ORDER BY id ASC
    ''', (f"-{hours}",))
    rows = cursor.fetchall()
    conn.close()
    
    result = [dict(row) for row in rows]
    if result and latest_traffic['timestamp'] is not None:
        last = result[-1]
        last['traffic_vivo_rx'] = latest_traffic['traffic_vivo_rx']
        last['traffic_vivo_tx'] = latest_traffic['traffic_vivo_tx']
        last['traffic_micks_rx'] = latest_traffic['traffic_micks_rx']
        last['traffic_micks_tx'] = latest_traffic['traffic_micks_tx']
        last['traffic_lan_rx'] = latest_traffic['traffic_lan_rx']
        last['traffic_lan_tx'] = latest_traffic['traffic_lan_tx']
        
    return jsonify(result)

@app.route('/api/data/latest', methods=['GET'])
def get_latest_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM telemetry ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({})
        
    result = dict(row)
    if latest_traffic['timestamp'] is not None:
        result['traffic_vivo_rx'] = latest_traffic['traffic_vivo_rx']
        result['traffic_vivo_tx'] = latest_traffic['traffic_vivo_tx']
        result['traffic_micks_rx'] = latest_traffic['traffic_micks_rx']
        result['traffic_micks_tx'] = latest_traffic['traffic_micks_tx']
        result['traffic_lan_rx'] = latest_traffic['traffic_lan_rx']
        result['traffic_lan_tx'] = latest_traffic['traffic_lan_tx']
        
    # Enriqecer com métricas radiológicas
    med_health = get_radiology_health_summary()
    result.update(med_health)
        
    return jsonify(result)

@app.route('/api/radiology/status', methods=['GET'])
def get_radiology_status():
    try:
        health = get_radiology_health_summary()
        return jsonify(health), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    days = request.args.get('days', 7, type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM incidents 
        WHERE timestamp >= datetime('now', ? || ' days')
        ORDER BY id DESC
        LIMIT 50
    ''', (f"-{days}",))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/traffic/stats', methods=['GET'])
def get_traffic_stats():
    try:
        peak_days = request.args.get('peak_days', 30, type=int)
        stats = calculate_traffic_stats(peak_days)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
