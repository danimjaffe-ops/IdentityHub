from .api_keys import api_keys_bp
from .auth import auth_bp
from .jira import jira_bp
from .tickets import tickets_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(jira_bp, url_prefix="/api/jira")
    app.register_blueprint(tickets_bp, url_prefix="/api/tickets")
    app.register_blueprint(api_keys_bp, url_prefix="/api/keys")
