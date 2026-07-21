import os
import sys
from services.telegram_service import send_telegram_message, send_laudite_alert

def main():
    print("=====================================================")
    print("  TESTADOR DE ALERTAS TELEGRAM - LAUDITE ASR MONITOR  ")
    print("=====================================================\n")

    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        print("⚠️ ATENÇÃO: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não estão configurados.")
        print("\nPara configurar no seu ambiente ou no PythonAnywhere:")
        print("  set TELEGRAM_BOT_TOKEN=seu_bot_token")
        print("  set TELEGRAM_CHAT_ID=seu_chat_id")
        print("\nExemplo de uso rápido para teste:")
        print("  python test_telegram_alert.py <BOT_TOKEN> <CHAT_ID>\n")
        
        if len(sys.argv) >= 3:
            os.environ['TELEGRAM_BOT_TOKEN'] = sys.argv[1]
            os.environ['TELEGRAM_CHAT_ID'] = sys.argv[2]
            print(f"Usando argumentos fornecidos via CLI...")
        else:
            return

    print("Enviando mensagem de teste de fluidez do Laudite ASR...")
    success, msg = send_laudite_alert(
        mos_score=3.4,
        mos_status="Atenção (Ligeira Latência)",
        jitter_ms=28.5,
        rtt_vivo=245.0,
        rtt_micks=260.0,
        rca_text="Teste de disparo de alerta de oscilação do Laudite ASR."
    )

    if success:
        print("\n✅ SUCESSO! Alerta enviado com sucesso para o seu Telegram!")
    else:
        print(f"\n❌ FALHA ao enviar mensagem: {msg}")

if __name__ == '__main__':
    main()
