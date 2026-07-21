import os
import sqlite3
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'telemetry.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Primary telemetry table
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
    
    # 2. Run safe column migrations
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
            
    # 3. Traffic accumulation table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic_accumulation (
            date TEXT PRIMARY KEY,
            vivo_rx INTEGER DEFAULT 0,
            vivo_tx INTEGER DEFAULT 0,
            micks_rx INTEGER DEFAULT 0,
            micks_tx INTEGER DEFAULT 0
        )
    ''')
    
    # 4. Incidents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            severity TEXT,
            message TEXT,
            rca TEXT
        )
    ''')
    
    # 5. Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp)")
    
    conn.commit()
    conn.close()

def prune_old_telemetry(days=90):
    """Purge telemetry records older than N days to optimize database size."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM telemetry WHERE timestamp < datetime('now', ?)", (f"-{days} days",))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count
    except Exception as e:
        print(f"Error pruning old telemetry: {e}")
        return 0

def parse_float(val, default=0.0):
    """Defensive float parsing supporting RouterOS 7 time interval strings (HH:MM:SS.ffffff)."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return default
    if ':' in val_str:
        try:
            parts = val_str.split(':')
            if len(parts) == 3:
                h = float(parts[0])
                m = float(parts[1])
                s = float(parts[2])
                total_seconds = h * 3600.0 + m * 60.0 + s
                return round(total_seconds * 1000.0, 1)
        except Exception:
            return default
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default

def parse_int(val, default=0):
    """Defensive int parsing."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def save_telemetry_record(data):
    """Sanitize input and save telemetry record into database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    link_ativo = str(data.get('link_ativo', 'VIVO')).upper()
    rtt_vivo_mm = parse_float(data.get('rtt_vivo_mm', data.get('MONITOR_VIVO_MOBILEMED', 0)))
    rtt_vivo_lf = parse_float(data.get('rtt_vivo_lf', data.get('MONITOR_VIVO_LIFEFOCUS', 0)))
    rtt_vivo_lp = parse_float(data.get('rtt_vivo_lp', data.get('MONITOR_VIVO_LIFEPLUS', 0)))
    rtt_micks_mm = parse_float(data.get('rtt_micks_mm', data.get('MONITOR_MICKS_MOBILEMED', 0)))
    rtt_micks_lf = parse_float(data.get('rtt_micks_lf', data.get('MONITOR_MICKS_LIFEFOCUS', 0)))
    rtt_micks_lp = parse_float(data.get('rtt_micks_lp', data.get('MONITOR_MICKS_LIFEPLUS', 0)))
    
    cpu = parse_int(data.get('cpu', 0))
    temp = parse_int(data.get('temp', 0))
    ram = parse_int(data.get('ram', 0))
    uptime = str(data.get('uptime', '0s'))
    
    traffic_vivo_rx = parse_float(data.get('traffic_vivo_rx', 0))
    traffic_vivo_tx = parse_float(data.get('traffic_vivo_tx', 0))
    traffic_micks_rx = parse_float(data.get('traffic_micks_rx', 0))
    traffic_micks_tx = parse_float(data.get('traffic_micks_tx', 0))
    traffic_lan_rx = parse_float(data.get('traffic_lan_rx', 0))
    traffic_lan_tx = parse_float(data.get('traffic_lan_tx', 0))
    
    dhcp_leases = parse_int(data.get('dhcp_active_leases', 0))
    eth1_speed = str(data.get('eth1_speed', '1Gbps'))
    eth2_speed = str(data.get('eth2_speed', '1Gbps'))
    eth1_errors = parse_int(data.get('eth1_errors', 0))
    eth2_errors = parse_int(data.get('eth2_errors', 0))
    logs = str(data.get('logs', ''))
    
    rtt_vivo_laudite = parse_float(data.get('rtt_vivo_laudite', data.get('MONITOR_VIVO_LAUDITE', 0)))
    rtt_micks_laudite = parse_float(data.get('rtt_micks_laudite', data.get('MONITOR_MICKS_LAUDITE', 0)))
    rtt_vivo_laudite_asr = parse_float(data.get('rtt_vivo_laudite_asr', data.get('MONITOR_VIVO_LAUDITE_ASR', 0)))
    rtt_micks_laudite_asr = parse_float(data.get('rtt_micks_laudite_asr', data.get('MONITOR_MICKS_LAUDITE_ASR', 0)))
    rtt_vivo_rbd = parse_float(data.get('rtt_vivo_rbd', data.get('MONITOR_VIVO_RBD', 0)))
    rtt_micks_rbd = parse_float(data.get('rtt_micks_rbd', data.get('MONITOR_MICKS_RBD', 0)))

    # Detect incidents before inserting
    cursor.execute('SELECT link_ativo FROM telemetry ORDER BY id DESC LIMIT 1')
    last_row = cursor.fetchone()
    
    # 1. LINK_FAILOVER — route switchover
    if last_row and last_row['link_ativo'] != link_ativo:
        inc_type = "LINK_FAILOVER"
        severity = "HIGH" if link_ativo == "MICKS" else "INFO"
        msg = f"Chaveamento de Rota: Operadora ativa alterada de {last_row['link_ativo']} para {link_ativo}"
        rca_details = []
        if cpu > 80: rca_details.append(f"Uso de CPU elevado no roteador ({cpu}%)")
        if traffic_lan_rx > 80000000 or traffic_lan_tx > 80000000: rca_details.append("Pico de tráfego intenso na rede LAN (>80Mbps)")
        if eth1_errors > 0: rca_details.append(f"Erros de CRC/físico na porta ether1 ({eth1_errors} erros)")
        if not rca_details: rca_details.append("Falha de ping nos testes de Netwatch da operadora principal")
        rca_text = " | ".join(rca_details)
        cursor.execute('INSERT INTO incidents (type, severity, message, rca) VALUES (?, ?, ?, ?)',
                       (inc_type, severity, msg, rca_text))
    
    # 2. LATENCY_SPIKE — RTT exceeds SLA threshold
    sla_checks = [
        ('MobileMed', rtt_vivo_mm, rtt_micks_mm, 150, 250),
        ('LifeFocus', rtt_vivo_lf, rtt_micks_lf, 280, 350),
        ('LifePlus', rtt_vivo_lp, rtt_micks_lp, 280, 350),
        ('Laudite ASR', rtt_vivo_laudite_asr, rtt_micks_laudite_asr, 250, 300),
        ('RBD PACS', rtt_vivo_rbd, rtt_micks_rbd, 150, 250),
    ]
    for dest_name, v_rtt, m_rtt, v_limit, m_limit in sla_checks:
        violations = []
        if v_rtt > v_limit: violations.append(f"VIVO {v_rtt:.1f}ms > {v_limit}ms")
        if m_rtt > m_limit: violations.append(f"MICKS {m_rtt:.1f}ms > {m_limit}ms")
        if violations:
            cursor.execute('INSERT INTO incidents (type, severity, message, rca) VALUES (?, ?, ?, ?)',
                           ("LATENCY_SPIKE", "MEDIUM",
                            f"Pico de Latência em {dest_name}: {', '.join(violations)}",
                            f"Violação de SLA detectada no destino {dest_name}"))
    
    # 3. DESTINATION_DOWN — RTT = 0 for a previously reachable destination
    if last_row:
        dest_down_checks = [
            ('MobileMed VIVO', rtt_vivo_mm, 'rtt_vivo_mm'),
            ('MobileMed MICKS', rtt_micks_mm, 'rtt_micks_mm'),
            ('RBD PACS VIVO', rtt_vivo_rbd, 'rtt_vivo_rbd'),
            ('RBD PACS MICKS', rtt_micks_rbd, 'rtt_micks_rbd'),
        ]
        for dest_name, current_rtt, col_name in dest_down_checks:
            prev_val = last_row[col_name] if col_name in last_row.keys() else 0
            if prev_val > 0 and current_rtt == 0:
                cursor.execute('INSERT INTO incidents (type, severity, message, rca) VALUES (?, ?, ?, ?)',
                               ("DESTINATION_DOWN", "HIGH",
                                f"Destino {dest_name} ficou inalcançável (RTT: {prev_val:.1f}ms → 0ms)",
                                f"Perda de conectividade para {dest_name}"))
    
    # 4. CPU_OVERLOAD — CPU > 85%
    if cpu > 85:
        cursor.execute('INSERT INTO incidents (type, severity, message, rca) VALUES (?, ?, ?, ?)',
                       ("CPU_OVERLOAD", "HIGH",
                        f"Sobrecarga de CPU do Roteador: {cpu}%",
                        f"Temperatura: {temp}°C | RAM: {ram}MB"))

    cursor.execute('''
        INSERT INTO telemetry (
            link_ativo, rtt_vivo_mm, rtt_vivo_lf, rtt_vivo_lp,
            rtt_micks_mm, rtt_micks_lf, rtt_micks_lp,
            cpu, temp, ram, uptime,
            traffic_vivo_rx, traffic_vivo_tx,
            traffic_micks_rx, traffic_micks_tx,
            traffic_lan_rx, traffic_lan_tx,
            dhcp_active_leases, eth1_speed, eth2_speed, eth1_errors, eth2_errors, logs,
            rtt_vivo_laudite, rtt_micks_laudite,
            rtt_vivo_laudite_asr, rtt_micks_laudite_asr,
            rtt_vivo_rbd, rtt_micks_rbd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        link_ativo, rtt_vivo_mm, rtt_vivo_lf, rtt_vivo_lp,
        rtt_micks_mm, rtt_micks_lf, rtt_micks_lp,
        cpu, temp, ram, uptime,
        traffic_vivo_rx, traffic_vivo_tx,
        traffic_micks_rx, traffic_micks_tx,
        traffic_lan_rx, traffic_lan_tx,
        dhcp_leases, eth1_speed, eth2_speed, eth1_errors, eth2_errors, logs,
        rtt_vivo_laudite, rtt_micks_laudite,
        rtt_vivo_laudite_asr, rtt_micks_laudite_asr,
        rtt_vivo_rbd, rtt_micks_rbd
    ))
    
    # Update traffic accumulation
    tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
    today_str = datetime.datetime.now(tz_gmt3).strftime('%Y-%m-%d')
    bytes_vivo_rx = int(traffic_vivo_rx * 5 / 8)
    bytes_vivo_tx = int(traffic_vivo_tx * 5 / 8)
    bytes_micks_rx = int(traffic_micks_rx * 5 / 8)
    bytes_micks_tx = int(traffic_micks_tx * 5 / 8)
    
    cursor.execute('''
        INSERT INTO traffic_accumulation (date, vivo_rx, vivo_tx, micks_rx, micks_tx)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            vivo_rx = vivo_rx + excluded.vivo_rx,
            vivo_tx = vivo_tx + excluded.vivo_tx,
            micks_rx = micks_rx + excluded.micks_rx,
            micks_tx = micks_tx + excluded.micks_tx
    ''', (today_str, bytes_vivo_rx, bytes_vivo_tx, bytes_micks_rx, bytes_micks_tx))
    
    conn.commit()
    conn.close()
