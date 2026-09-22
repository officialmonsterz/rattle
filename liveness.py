"""
Token liveness worker.

A daemon thread that periodically re-spends every stored refresh token
against Google's token endpoint. Tokens that still refresh are marked
"valid" (and their access_token is updated); revoked/expired ones are
marked "dead"; anything else stays "unknown".
"""

import logging
import threading
import time
from datetime import timedelta

import requests

from models import Token, db, utcnow

log = logging.getLogger("rattle.liveness")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def check_all_tokens(app):
    """Refresh every captured refresh token; update status + last_checked."""
    with app.app_context():
        tokens = Token.query.filter(Token.refresh_token.isnot(None)).all()
        tokens = [t for t in tokens if t.refresh_token]
        checked = 0
        for tok in tokens:
            campaign = tok.campaign
            if not campaign:
                continue
            try:
                resp = requests.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": campaign.client_id,
                        "client_secret": campaign.client_secret,
                        "refresh_token": tok.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    timeout=15,
                )
            except requests.RequestException:
                log.exception("liveness network error for token %s", tok.id)
                continue

            tok.last_checked = utcnow()
            if resp.status_code == 200:
                data = resp.json()
                tok.access_token = data.get("access_token", tok.access_token)
                expires_in = data.get("expires_in")
                if expires_in:
                    tok.expires_in = int(expires_in)
                    tok.expiry_time = utcnow() + timedelta(seconds=int(expires_in))
                tok.status = "valid"
                tok.is_active = True
            elif resp.status_code in (400, 401, 403):
                # invalid_grant / revoked / expired -> the token is dead
                tok.status = "dead"
                tok.is_active = False
            else:
                tok.status = "unknown"
            checked += 1

        try:
            db.session.commit()
            log.info("liveness check done: %d tokens checked", checked)
        except Exception:
            db.session.rollback()
            log.exception("liveness commit failed")


def _worker(app, interval_minutes):
    interval = max(1, int(interval_minutes)) * 60
    while True:
        try:
            check_all_tokens(app)
        except Exception:
            log.exception("liveness worker crashed; will retry next cycle")
        time.sleep(interval)


def start_liveness_worker(app):
    """Start the daemon thread once. Guards against double-start on reload."""
    if getattr(app, "_liveness_started", False):
        return
    app._liveness_started = True
    # app.config is a dict -> read with .get()
    interval = app.config.get("TOKEN_CHECK_INTERVAL_MINUTES", 30) or 30
    t = threading.Thread(
        target=_worker,
        args=(app, interval),
        daemon=True,
        name="rattle-liveness",
    )
    t.start()
    log.info("token liveness worker started (every %s minutes)", interval)
