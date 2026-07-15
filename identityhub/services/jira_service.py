from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from .crypto_service import decrypt
from ..utils.errors import JiraError, JiraUnavailableError


def _normalize_created(value):
    """Convert Jira's created timestamp (e.g. '2026-07-14T18:00:00.000+0000')
    to ISO 8601 with a colon offset, matching the local Ticket.to_dict format.
    Falls back to the raw value if it can't be parsed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z").isoformat()
    except (ValueError, TypeError):
        return value


class JiraService:
    """Wrapper around Jira Cloud REST API v3."""

    def __init__(self, credential):
        self.base_url = credential.site_url.rstrip("/")
        self.auth = HTTPBasicAuth(
            decrypt(credential.email_encrypted),
            decrypt(credential.api_token_encrypted),
        )
        self.timeout = 15

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}/rest/api/3{path}"
        try:
            resp = requests.request(
                method, url, auth=self.auth, timeout=self.timeout, **kwargs
            )
        except requests.ConnectionError:
            raise JiraUnavailableError(f"Cannot connect to Jira at {self.base_url}")
        except requests.Timeout:
            raise JiraUnavailableError("Jira request timed out")

        if resp.status_code == 401:
            raise JiraError("Jira authentication failed — check your credentials")
        if resp.status_code == 403:
            raise JiraError("Jira access denied — check your permissions")
        if resp.status_code >= 500:
            raise JiraUnavailableError(
                f"Jira is unavailable (HTTP {resp.status_code})"
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("errorMessages", [])
            except (ValueError, requests.exceptions.JSONDecodeError):
                raise JiraError(
                    "Unexpected response from Jira. "
                    "Verify your Site URL is correct (e.g. https://your-org.atlassian.net)"
                )
            raise JiraError(
                f"Jira API error: {'; '.join(str(m) for m in detail)}"
                if detail
                else f"Jira request failed (HTTP {resp.status_code})"
            )

        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise JiraError(
                f"Unexpected response from Jira (got {content_type or 'no content-type'}). "
                "Verify your Site URL is correct (e.g. https://your-org.atlassian.net)"
            )

        try:
            return resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            raise JiraError("Jira returned an invalid response. Verify your Site URL is correct.")

    def test_connection(self):
        return self._request("GET", "/myself")

    def list_projects(self):
        data = self._request("GET", "/project")
        return [{"key": p["key"], "name": p["name"], "id": p["id"]} for p in data]

    def create_issue(self, project_key, summary, description="", issue_type="Task"):
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description or ""}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }
        result = self._request("POST", "/issue", json=payload)
        return {"key": result["key"], "id": result["id"]}

    def search_recent(self, project_key=None, limit=10):
        """Return the current user's most recently created issues, live from Jira.

        Because this reads directly from Jira, issues deleted in Jira no longer
        appear. Optionally scoped to a single project. Results are shaped to match
        Ticket.to_dict so the frontend can render them interchangeably.
        """
        limit = min(max(int(limit), 1), 100)

        clauses = ["reporter = currentUser()"]
        if project_key:
            escaped = project_key.replace('"', '\\"')
            clauses.insert(0, f'project = "{escaped}"')
        jql = " AND ".join(clauses) + " ORDER BY created DESC"

        params = {
            "jql": jql,
            "maxResults": limit,
            "fields": "summary,created,project",
        }
        data = self._request("GET", "/search/jql", params=params)

        results = []
        for issue in data.get("issues", []):
            fields = issue.get("fields") or {}
            project = fields.get("project") or {}
            issue_id = issue.get("id")
            try:
                numeric_id = int(issue_id)
            except (TypeError, ValueError):
                numeric_id = None
            results.append(
                {
                    "id": numeric_id,
                    "jira_key": issue.get("key"),
                    "jira_id": issue_id,
                    "project_key": project.get("key", project_key),
                    "summary": fields.get("summary", ""),
                    "description": None,
                    "source": "jira",
                    "created_at": _normalize_created(fields.get("created")),
                }
            )
        return results
