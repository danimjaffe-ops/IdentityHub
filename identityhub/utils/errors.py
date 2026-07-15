from flask import jsonify


class AppError(Exception):
    """Base application error."""

    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["error"] = self.__class__.__name__
        rv["message"] = self.message
        return rv


class ValidationError(AppError):
    status_code = 400


class AuthenticationError(AppError):
    status_code = 401


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class JiraError(AppError):
    status_code = 502


class JiraUnavailableError(JiraError):
    """Jira could not be reached (connection failure, timeout, or 5xx).

    Distinct from JiraError so callers can degrade gracefully on an outage
    while still surfacing genuine errors like bad credentials.
    """

    status_code = 503


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_405(error):
        return jsonify(
            {"error": "method_not_allowed", "message": "Method not allowed"}
        ), 405

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify(
            {"error": "internal_error", "message": "An internal error occurred"}
        ), 500
