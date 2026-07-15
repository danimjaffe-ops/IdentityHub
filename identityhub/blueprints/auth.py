from flask import Blueprint, jsonify, request
from flask_login import current_user, logout_user

from ..extensions import db
from ..middleware.auth import require_session, start_user_session
from ..models.user import User
from ..utils.errors import ConflictError, ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password")

    if not email or "@" not in email:
        raise ValidationError("A valid email is required")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    # confirm_password is a UX guardrail against typos. The client always sends
    # it; when present it must match so a mistyped pair can't create an account.
    if confirm_password is not None and confirm_password != password:
        raise ValidationError("Passwords do not match")

    if User.query.filter_by(email=email).first():
        raise ConflictError("An account with this email already exists")

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    start_user_session(user)
    return jsonify({"user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        raise ValidationError("Email and password are required")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        raise ValidationError("Invalid email or password")

    start_user_session(user)
    return jsonify({"user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@require_session
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@auth_bp.route("/account", methods=["DELETE"])
@require_session
def delete_account():
    user = current_user._get_current_object()
    db.session.delete(user)
    db.session.commit()
    logout_user()
    return jsonify({"message": "Account deleted"}), 200


@auth_bp.route("/me", methods=["GET"])
@require_session
def me():
    return jsonify(current_user.to_dict())
