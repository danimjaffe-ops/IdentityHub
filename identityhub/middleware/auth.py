import hashlib
from datetime import datetime, timezone
from functools import wraps

from flask import g, jsonify, request, session
from flask_login import current_user, login_user

from ..extensions import db
from ..models.api_key import ApiKey

# Session key holding the ISO-8601 UTC timestamp of when the session began.
# Used to enforce the absolute session timeout.
SESSION_STARTED_KEY = "login_at"


def start_user_session(user):
    """Log the user in and stamp the session start time.

    The timestamp anchors the absolute session timeout enforced in
    ``enforce_absolute_session_timeout`` (identityhub/__init__.py).
    """
    login_user(user)
    session.permanent = True
    session[SESSION_STARTED_KEY] = datetime.now(timezone.utc).isoformat()


def require_session(f):
    """Decorator that requires an authenticated session (cookie-based)."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(
                {"error": "authentication_required", "message": "Login required"}
            ), 401
        g.current_user = current_user
        g.auth_method = "session"
        return f(*args, **kwargs)

    return decorated


def require_auth(f):
    """Decorator that accepts either session auth or API key auth."""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Try session first
        if current_user.is_authenticated:
            g.current_user = current_user
            g.auth_method = "session"
            return f(*args, **kwargs)

        # Try API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            key_record = db.session.execute(
                db.select(ApiKey).where(
                    ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
                )
            ).scalar_one_or_none()

            if key_record:
                from datetime import datetime, timezone

                key_record.last_used_at = datetime.now(timezone.utc)
                db.session.commit()

                g.current_user = key_record.user
                g.auth_method = "api_key"
                return f(*args, **kwargs)

        return jsonify(
            {"error": "authentication_required", "message": "Login required"}
        ), 401

    return decorated
