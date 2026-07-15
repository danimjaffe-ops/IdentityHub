from flask import Blueprint, g, jsonify, request

from ..middleware.auth import require_auth
from ..models.jira_credential import JiraCredential
from ..services.jira_service import JiraService
from ..utils.errors import JiraUnavailableError, NotFoundError, ValidationError

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("", methods=["POST"])
@require_auth
def create_ticket():
    data = request.get_json(silent=True) or {}
    project_key = data.get("project_key", "").strip().upper()
    summary = data.get("summary", "").strip()
    description = data.get("description", "").strip()

    if not project_key:
        raise ValidationError("project_key is required")
    if not summary:
        raise ValidationError("summary is required")
    if len(summary) > 500:
        raise ValidationError("summary must be 500 characters or fewer")

    cred = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if not cred:
        raise NotFoundError("Connect your Jira workspace first")

    result = JiraService(cred).create_issue(project_key, summary, description)

    # Jira is the single source of truth — we do not persist a local copy.
    source = "api" if g.auth_method == "api_key" else "web"
    return (
        jsonify(
            {
                "jira_key": result["key"],
                "jira_id": result["id"],
                "project_key": project_key,
                "summary": summary,
                "description": description or None,
                "source": source,
            }
        ),
        201,
    )


@tickets_bp.route("", methods=["GET"])
@require_auth
def list_tickets():
    project_key = request.args.get("project_key", "").strip().upper()
    limit = request.args.get("limit", 10, type=int)
    limit = min(max(limit, 1), 100)

    # Recent Tickets is served live from Jira, so tickets deleted in Jira
    # disappear immediately. Without a Jira connection there is nothing to query.
    cred = JiraCredential.query.filter_by(user_id=g.current_user.id).first()
    if not cred:
        return jsonify({"tickets": [], "unavailable": False})

    try:
        tickets = JiraService(cred).search_recent(project_key, limit)
        return jsonify({"tickets": tickets, "unavailable": False})
    except JiraUnavailableError:
        # Jira is unreachable. Since Jira is the sole source of truth there is no
        # local cache to fall back on — return an explicit unavailable state so
        # the dashboard shows a notice instead of failing. Auth/permission errors
        # are NOT caught here and still surface to the user.
        return jsonify({"tickets": [], "unavailable": True})
