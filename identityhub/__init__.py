import os
from datetime import datetime, timezone

from flask import Flask, jsonify, send_from_directory, session
from flask_login import logout_user

from .api_docs import register_api_docs
from .extensions import db, migrate, login_manager, cors


def create_app(config_name=None):
    app = Flask(__name__, static_folder=None)

    config_map = {
        "development": "config.DevelopmentConfig",
        "testing": "config.TestingConfig",
        "e2e": "config.E2ETestingConfig",
        "production": "config.ProductionConfig",
    }
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map.get(config_name, config_map["development"]))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cors.init_app(app, supports_credentials=True, origins=["http://localhost:5173"])

    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        from .models.user import User

        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return {"error": "authentication_required", "message": "Login required"}, 401

    from .middleware.auth import SESSION_STARTED_KEY

    @app.before_request
    def enforce_absolute_session_timeout():
        """Expire a session once PERMANENT_SESSION_LIFETIME has elapsed since
        login, regardless of activity (absolute, not idle, timeout).

        Keyed off the session cookie itself (not ``current_user``): the timeout
        is a property of the session, and API-key/anonymous requests carry no
        login session, so they are unaffected."""
        if "_user_id" not in session:
            return None

        started = None
        started_raw = session.get(SESSION_STARTED_KEY)
        if started_raw:
            try:
                started = datetime.fromisoformat(started_raw)
            except (TypeError, ValueError):
                started = None

        now = datetime.now(timezone.utc)
        lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
        if started is None or now - started > lifetime:
            logout_user()
            session.clear()
            return jsonify(
                {
                    "error": "session_expired",
                    "message": "Your session has expired. Please log in again.",
                }
            ), 401
        return None

    from .blueprints import register_blueprints

    register_blueprints(app)

    from .utils.errors import register_error_handlers

    register_error_handlers(app)

    from .cli import register_cli_commands

    register_cli_commands(app)

    register_api_docs(app)

    # Serve React SPA in production
    frontend_dist = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "frontend", "dist"
    )

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        if path.startswith("api/"):
            from flask import abort

            abort(404)
        full_path = os.path.join(frontend_dist, path)
        if path and os.path.isfile(full_path):
            return send_from_directory(frontend_dist, path)
        index = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index):
            return send_from_directory(frontend_dist, "index.html")
        return {
            "message": "IdentityHub API. Frontend not built — run 'make build'."
        }, 200

    return app
