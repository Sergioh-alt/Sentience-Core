"""
EEA-2026-ANT: core/alerts.py
Sistema de alertas multi-canal y Control Remoto.
Soporta Telegram (gratis).
"""
import os
import requests
import logging
import time

log = logging.getLogger("EEA-2026")

# Variable global para rastrear el último mensaje leído
LAST_UPDATE_ID = 0

def send_alert(message, level="INFO"):
    """
    Envía alertas a Telegram. Silencioso si no hay token configurado.
    Niveles: INFO, BUY, SELL, STOP, ERROR, SYSTEM
    """
    _send_telegram(message, level)


def _send_telegram(message, level):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    icons = {
        "INFO": "[INFO]",
        "BUY": "[BUY]",
        "SELL": "[SELL]",
        "STOP": "[STOP]",
        "ERROR": "[ERR]",
        "SYSTEM": "[SYS]",
        "SECURITY": "[GUARD]"
    }
    icon = icons.get(level, "[NOTE]")

    try:
        text = f"{icon} *EEA-2026-ANT*\n{message}"
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=5
        )
    except Exception:
        pass


def poll_telegram_commands():
    """
    Lee los últimos mensajes de Telegram buscando comandos.
    Retorna 'START', 'STOP', o None.
    """
    global LAST_UPDATE_ID
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return None

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"offset": LAST_UPDATE_ID + 1, "timeout": 2}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data.get("result"):
                results = data["result"]
                latest_command = None
                
                for item in results:
                    LAST_UPDATE_ID = item["update_id"]
                    message = item.get("message", {}).get("text", "").lower().strip()
                    
                    if message == "/start":
                        latest_command = "START"
                    elif message == "/stop":
                        latest_command = "STOP"
                    elif message == "/report":
                        latest_command = "REPORT"
                    elif message == "/url":
                        latest_command = "URL"
                    elif message == "/help":
                        latest_command = "HELP"
                    elif message == "/status":
                        latest_command = "STATUS"
                    elif message.startswith("/yes_") or message.startswith("/no_"):
                        latest_command = message[1:].upper() # Retorna YES_BTC o NO_BTC por ejemplo
                
                return latest_command
    except Exception:
        pass
    
    return None
