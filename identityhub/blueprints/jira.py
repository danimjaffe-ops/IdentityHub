from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..middleware.auth import require_session
from ..models.jira_credential import JiraCredential
from ..services.crypto_service import decrypt, encrypt
from ..services.jira_service import JiraService
from ..utils.errors import NotFoundError, ValidationError

jira_bp = Blueprint("jira", __name__)


@jira_bp.route("/credentials", methods=["POST"])
@require_session
def connect():
    data = request.get_json(silent=True) or {}
    site_url = data.get("site_url", "").strip().rstrip("/")
    email = data.get("email", "").strip()
    api_token = data.get("api_token", "").strip()

    if not site_url:
        raise ValidationError("Jira site URL is required")
    if not site_url.startswith("https://"):
        raise ValidationError("Jira site URL must start with https://")
    if not email:
        raise ValidationError("Jira email is required")
    if not api_token:
        raise ValidationError("Jira API token is required")

    cred = JiraCredential(
        user_id=g.current_user.id,
        site_url=site_url,
        email_encrypted=encrypt(email),
        api_token_encrypted=encrypt(api_token),
    )
    service = JiraService(cred)
    service.test_connection()

    existing = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if existing:
        existing.site_url = site_url
        existing.email_encrypted = encrypt(email)
        existing.api_token_encrypted = encrypt(api_token)
    else:
        db.session.add(cred)

    db.session.commit()

    return jsonify({
        "connected": True,
        "site_url": site_url,
        "email_masked": _mask_email(email),
    }), 201


@jira_bp.route("/status", methods=["GET"])
@require_session
def status():
    cred = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if not cred:
        return jsonify({"connected": False, "site_url": None, "email_masked": None})

    email = decrypt(cred.email_encrypted)
    return jsonify({
        "connected": True,
        "site_url": cred.site_url,
        "email_masked": _mask_email(email),
    })


@jira_bp.route("/credentials", methods=["DELETE"])
@require_session
def disconnect():
    cred = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if not cred:
        raise NotFoundError("No Jira credentials found")

    db.session.delete(cred)
    db.session.commit()
    return jsonify({"message": "Jira credentials removed"})


@jira_bp.route("/projects", methods=["GET"])
@require_session
def projects():
    cred = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if not cred:
        raise NotFoundError("Connect your Jira workspace first")

    service = JiraService(cred)
    project_list = service.list_projects()
    return jsonify({"projects": project_list})


def _mask_email(email):
    parts = email.split("@")
    if len(parts) != 2:
        return "***"
    local = parts[0]
    masked = local[0] + "***" if len(local) > 1 else "***"
    return f"{masked}@{parts[1]}"
