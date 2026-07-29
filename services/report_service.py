import csv
import io
import datetime
from db import get_db_connection

def generate_isp_sla_report(days=30):
    """
    Generates formal ISP SLA Audit Report for commercial dispute / claim against VIVO & MICKS.
    Calculates total operational time, outage minutes, latency SLA breach minutes,
    percentage compliance, and affected medical endpoints.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    since_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('SELECT COUNT(*) FROM telemetry WHERE timestamp >= ?', (since_date,))
    total_samples = cursor.fetchone()[0] or 0
    
    # 5-minute sampling intervals assumed per telemetry record
    sample_interval_sec = 300
    total_seconds = total_samples * sample_interval_sec
    total_hours = round(total_seconds / 3600.0, 1)
    
    destinations = [
        ('mm', 'MobileMed PACS', 'rtt_vivo_mm', 'rtt_micks_mm', 150, 250),
        ('rbd', 'RBD PACS', 'rtt_vivo_rbd', 'rtt_micks_rbd', 150, 250),
        ('lf', 'LifeFocus', 'rtt_vivo_lf', 'rtt_micks_lf', 280, 350),
        ('lp', 'LifePlus', 'rtt_vivo_lp', 'rtt_micks_lp', 280, 350),
        ('lda', 'Laudite ASR Speech', 'rtt_vivo_laudite_asr', 'rtt_micks_laudite_asr', 250, 300),
    ]
    
    report_rows = []
    vivo_total_breaches = 0
    micks_total_breaches = 0
    vivo_down_count = 0
    micks_down_count = 0
    
    for key, name, vivo_col, micks_col, vivo_limit, micks_limit in destinations:
        cursor.execute(f'''
            SELECT 
                COUNT(*),
                SUM(CASE WHEN {vivo_col} > 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN {micks_col} > 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN {vivo_col} > {vivo_limit} THEN 1 ELSE 0 END),
                SUM(CASE WHEN {micks_col} > {micks_limit} THEN 1 ELSE 0 END),
                AVG(CASE WHEN {vivo_col} > 0 THEN {vivo_col} END),
                AVG(CASE WHEN {micks_col} > 0 THEN {micks_col} END),
                MAX({vivo_col}),
                MAX({micks_col})
            FROM telemetry WHERE timestamp >= ?
        ''', (since_date,))
        row = cursor.fetchone()
        
        cnt = row[0] or 0
        v_up = row[1] or 0
        m_up = row[2] or 0
        v_breach = row[3] or 0
        m_breach = row[4] or 0
        v_avg = round(row[5], 1) if row[5] else 0.0
        m_avg = round(row[6], 1) if row[6] else 0.0
        v_max = round(row[7], 1) if row[7] else 0.0
        m_max = round(row[8], 1) if row[8] else 0.0
        
        v_down = cnt - v_up
        m_down = cnt - m_up
        
        v_sla_pct = round(((cnt - v_breach - v_down) / cnt * 100.0), 2) if cnt > 0 else 100.0
        m_sla_pct = round(((cnt - m_breach - m_down) / cnt * 100.0), 2) if cnt > 0 else 100.0
        
        v_breach_mins = round((v_breach * sample_interval_sec) / 60.0, 1)
        m_breach_mins = round((m_breach * sample_interval_sec) / 60.0, 1)
        v_down_mins = round((v_down * sample_interval_sec) / 60.0, 1)
        m_down_mins = round((m_down * sample_interval_sec) / 60.0, 1)
        
        vivo_total_breaches += v_breach
        micks_total_breaches += m_breach
        vivo_down_count += v_down
        micks_down_count += m_down
        
        report_rows.append({
            "destination": name,
            "vivo_limit_ms": vivo_limit,
            "vivo_avg_rtt_ms": v_avg,
            "vivo_max_rtt_ms": v_max,
            "vivo_breach_mins": v_breach_mins,
            "vivo_down_mins": v_down_mins,
            "vivo_sla_compliance_pct": v_sla_pct,
            "micks_limit_ms": micks_limit,
            "micks_avg_rtt_ms": m_avg,
            "micks_max_rtt_ms": m_max,
            "micks_breach_mins": m_breach_mins,
            "micks_down_mins": m_down_mins,
            "micks_sla_compliance_pct": m_sla_pct,
        })
        
    conn.close()
    
    # Global summary calculations
    overall_vivo_sla = round(sum(r['vivo_sla_compliance_pct'] for r in report_rows) / len(report_rows), 2) if report_rows else 100.0
    overall_micks_sla = round(sum(r['micks_sla_compliance_pct'] for r in report_rows) / len(report_rows), 2) if report_rows else 100.0
    
    vivo_total_impact_mins = round((vivo_total_breaches + vivo_down_count) * sample_interval_sec / 60.0, 1)
    micks_total_impact_mins = round((micks_total_breaches + micks_down_count) * sample_interval_sec / 60.0, 1)
    
    # Generate CSV Output
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['RELATORIO DE AUDITORIA E CONTESTACAO DE SLA DE OPERADORAS DE INTERNET'])
    writer.writerow(['Periodo Analisado', f'Ultimos {days} dias', f'Total de Amostras: {total_samples} ({total_hours} horas)'])
    writer.writerow(['Data do Relatorio', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    writer.writerow(['RESUMO EXECUTIVO'])
    writer.writerow(['Operadora', 'Conformidade SLA Geral (%)', 'Minutos Fora do SLA (Latencia)', 'Minutos Indisponivel (Queda)', 'Impacto Total (Minutos)'])
    writer.writerow(['VIVO FIBRA', f'{overall_vivo_sla}%', round(vivo_total_breaches * 5, 1), round(vivo_down_count * 5, 1), vivo_total_impact_mins])
    writer.writerow(['MICKS TELECOM', f'{overall_micks_sla}%', round(micks_total_breaches * 5, 1), round(micks_down_count * 5, 1), micks_total_impact_mins])
    writer.writerow([])
    writer.writerow(['DETALHAMENTO POR DESTINO MEDICO'])
    writer.writerow([
        'Destino', 'Limite VIVO (ms)', 'Media VIVO (ms)', 'Max VIVO (ms)', 'VIVO Fora SLA (min)', 'VIVO Queda (min)', 'VIVO SLA (%)',
        'Limite MICKS (ms)', 'Media MICKS (ms)', 'Max MICKS (ms)', 'MICKS Fora SLA (min)', 'MICKS Queda (min)', 'MICKS SLA (%)'
    ])
    
    for r in report_rows:
        writer.writerow([
            r['destination'], r['vivo_limit_ms'], r['vivo_avg_rtt_ms'], r['vivo_max_rtt_ms'],
            r['vivo_breach_mins'], r['vivo_down_mins'], f"{r['vivo_sla_compliance_pct']}%",
            r['micks_limit_ms'], r['micks_avg_rtt_ms'], r['micks_max_rtt_ms'],
            r['micks_breach_mins'], r['micks_down_mins'], f"{r['micks_sla_compliance_pct']}%"
        ])
        
    csv_string = output.getvalue()
    
    return {
        "summary": {
            "days": days,
            "total_samples": total_samples,
            "total_hours": total_hours,
            "generated_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "overall_vivo_sla_pct": overall_vivo_sla,
            "overall_micks_sla_pct": overall_micks_sla,
            "vivo_impact_mins": vivo_total_impact_mins,
            "micks_impact_mins": micks_total_impact_mins,
        },
        "details": report_rows,
        "csv_text": csv_string
    }

def export_incidents_csv(days=30, inc_type=None):
    """
    Exports incidents log to CSV format for audit trails.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT id, timestamp, type, severity, message, rca FROM incidents WHERE timestamp >= datetime("now", ? || " days")'
    params = [f"-{days}"]
    if inc_type and inc_type != 'ALL':
        query += ' AND type = ?'
        params.append(inc_type)
    query += ' ORDER BY id DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Data/Hora', 'Tipo Incidente', 'Severidade', 'Mensagem', 'Causa Raiz (RCA)'])
    
    for r in rows:
        writer.writerow([r['id'], r['timestamp'], r['type'], r['severity'], r['message'], r['rca'] or ''])
        
    return output.getvalue()
