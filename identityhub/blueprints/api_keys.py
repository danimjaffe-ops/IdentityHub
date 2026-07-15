import hashlib
import secrets

from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..middleware.auth import require_session
from ..models.api_key import ApiKey
from ..utils.errors import NotFoundError, ValidationError

api_keys_bp = Blueprint("api_keys", __name__)


@api_keys_bp.route("", methods=["POST"])
@require_session
def generate_key():
    data = request.get_json(silent=True) or {}
    label = data.get("label", "").strip() or None

    if label and len(label) > 100:
        raise ValidationError("Label must be 100 characters or fewer")

    raw = secrets.token_hex(32)
    key = f"nhk_{raw}"
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    key_prefix = key[:12]

    api_key = ApiKey(
        user_id=g.current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        label=label,
    )
    db.session.add(api_key)
    db.session.commit()

    result = api_key.to_dict()
    result["key"] = key
    return jsonify(result), 201


@api_keys_bp.route("", methods=["GET"])
@require_session
def list_keys():
    keys = ApiKey.query.filter_by(
        user_id=g.current_user.id, is_active=True
    ).order_by(ApiKey.created_at.desc()).all()
    return jsonify({"keys": [k.to_dict() for k in keys]})


@api_keys_bp.route("/<int:key_id>", methods=["DELETE"])
@require_session
def revoke_key(key_id):
    api_key = ApiKey.query.filter_by(
        id=key_id, user_id=g.current_user.id
    ).first()
    if not api_key:
        raise NotFoundError("API key not found")

    api_key.is_active = False
    db.session.commit()
    return jsonify({"message": "API key revoked"})
