import os
import time
import json
import urllib.request
import urllib.parse
import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Cooldown tracking: status_type -> timestamp
_last_alert_timestamps = {}
COOLDOWN_SECONDS = 600  # 10 minutes cooldown between duplicate warnings

def send_telegram_message(message_text, parse_mode='Markdown'):
    """
    Send a message via Telegram Bot API using urllib.
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN)
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    
    if not token or not chat_id:
        print("[Telegram Alert Skipped] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        return False, "Token or Chat ID missing"
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": parse_mode
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.getcode() == 200:
                print("[Telegram Alert Sent] Message successfully delivered.")
                return True, "Success"
            else:
                print(f"[Telegram Alert Error] HTTP {resp.getcode()}")
                return False, f"HTTP {resp.getcode()}"
    except Exception as e:
        print(f"[Telegram Alert Exception] {e}")
        return False, str(e)

def send_laudite_alert(mos_score, mos_status, jitter_ms, rtt_vivo, rtt_micks, rca_text):
    """
    Evaluates Laudite ASR health and dispatches Telegram alerts with anti-spam cooldown.
    """
    global _last_alert_timestamps
    now = time.time()
    
    # 1. Evaluate degradation
    is_degraded = (mos_score < 3.8) or (jitter_ms > 20.0) or (rtt_vivo > 300 and rtt_micks > 300)
    
    last_degraded_time = _last_alert_timestamps.get('laudite_degraded', 0)
    last_was_degraded = _last_alert_timestamps.get('is_currently_degraded', False)
    
    tz_gmt3 = datetime.timezone(datetime.timedelta(hours=-3))
    now_str = datetime.datetime.now(tz_gmt3).strftime('%Y-%m-%d %H:%M:%S')
    
    if is_degraded:
        # Check cooldown (10 minutes)
        if last_was_degraded and (now - last_degraded_time < COOLDOWN_SECONDS):
            print(f"[Telegram Alert Cooldown] Alert suppressed (next in {int(COOLDOWN_SECONDS - (now - last_degraded_time))}s)")
            return False, "Cooldown active"
            
        _last_alert_timestamps['laudite_degraded'] = now
        _last_alert_timestamps['is_currently_degraded'] = True
        
        msg = (
            "🚨 *ALERTA DE FLUIDEZ LAUDITE ASR* 🎙️\n\n"
            f"⚠️ *Status:* {mos_status}\n"
            f"📊 *Score MOS (G.107):* `{mos_score} / 5.0`\n"
            f"〰️ *Jitter de Áudio:* `{jitter_ms} ms`\n"
            f"⚡ *RTT ASR:* VIVO `{rtt_vivo} ms` | MICKS `{rtt_micks} ms`\n\n"
            f"💡 *Diagnóstico:* {rca_text}\n"
            f"📅 *Data/Hora:* `{now_str}`"
        )
        return send_telegram_message(msg)
        
    elif last_was_degraded:
        # Recovery notification!
        _last_alert_timestamps['is_currently_degraded'] = False
        _last_alert_timestamps['laudite_degraded'] = 0
        
        msg = (
            "🟢 *FLUIDEZ LAUDITE RESTABELECIDA* 🎙️\n\n"
            f"✅ *Status:* Ditado Fluido\n"
            f"📊 *Score MOS (G.107):* `{mos_score} / 5.0`\n"
            f"〰️ *Jitter de Áudio:* `{jitter_ms} ms`\n"
            f"⚡ *RTT ASR:* VIVO `{rtt_vivo} ms` | MICKS `{rtt_micks} ms`\n\n"
            f"💡 *Diagnóstico:* Qualidade de voz normalizada em capacidade máxima.\n"
            f"📅 *Data/Hora:* `{now_str}`"
        )
        return send_telegram_message(msg)
        
    return False, "Normal state, no alert required"
