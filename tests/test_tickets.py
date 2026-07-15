"""Tests for the tickets blueprint (/api/tickets)."""

from unittest.mock import MagicMock, patch

import requests

from identityhub.models.jira_credential import JiraCredential
from identityhub.services.crypto_service import encrypt


def _register_and_login(client):
    """Helper: register a user and return the response (user stays logged in)."""
    return client.post(
        "/api/auth/register",
        json={"email": "ticket-user@example.com", "password": "password123"},
    )


def _add_jira_credential(db, user_id):
    """Helper: add a Jira credential for the given user.

    Must be called while an app context is already active (e.g. via the db fixture).
    """
    cred = JiraCredential(
        user_id=user_id,
        site_url="https://test.atlassian.net",
        email_encrypted=encrypt("jira@example.com"),
        api_token_encrypted=encrypt("token123"),
    )
    db.session.add(cred)
    db.session.commit()
    return cred


def _mock_jira_create():
    """Return a mock for requests.request that handles create_issue and test_connection."""
    return _mock_jira()


def _jira_issue(key, summary, project_key, issue_id, created="2026-07-14T18:00:00.000+0000"):
    """Build a Jira search issue payload as returned by /rest/api/3/search/jql."""
    return {
        "id": issue_id,
        "key": key,
        "fields": {
            "summary": summary,
            "created": created,
            "project": {"key": project_key},
        },
    }


def _mock_jira(search_issues=None):
    """Return a mock for requests.request covering the Jira endpoints the app uses.

    /search/jql returns `search_issues` (default: none), filtered by the project
    named in the JQL so tests can simulate an issue being deleted in Jira.
    """
    search_issues = search_issues or []
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "application/json"}

    def side_effect(method, url, **kwargs):
        mock_resp.status_code = 200
        if "/myself" in url:
            mock_resp.json.return_value = {"displayName": "Test User"}
        elif "/search/jql" in url:
            jql = kwargs.get("params", {}).get("jql", "")
            issues = [
                i
                for i in search_issues
                if "project =" not in jql
                or f'project = "{i["fields"]["project"]["key"]}"' in jql
            ]
            mock_resp.json.return_value = {"issues": issues}
        elif "/issue" in url:
            mock_resp.json.return_value = {"key": "TEST-1", "id": "10001"}
        elif "/project" in url:
            mock_resp.json.return_value = [
                {"key": "TEST", "name": "Test Project", "id": "1"}
            ]
        return mock_resp

    return side_effect


class TestCreateTicketAuth:
    """POST /api/tickets -- authentication checks."""

    def test_requires_auth(self, client, db):
        resp = client.post(
            "/api/tickets",
            json={
                "project_key": "TEST",
                "summary": "A ticket",
            },
        )
        assert resp.status_code == 401

    def test_validation_missing_project_key(self, client, db, app):
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.post(
            "/api/tickets",
            json={"summary": "Missing project key"},
        )
        assert resp.status_code == 400
        assert "project_key" in resp.get_json()["message"]

    def test_validation_missing_summary(self, client, db, app):
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.post(
            "/api/tickets",
            json={"project_key": "TEST"},
        )
        assert resp.status_code == 400
        assert "summary" in resp.get_json()["message"]

    def test_validation_summary_too_long(self, client, db, app):
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.post(
            "/api/tickets",
            json={"project_key": "TEST", "summary": "x" * 501},
        )
        assert resp.status_code == 400
        assert "500" in resp.get_json()["message"]

    def test_no_jira_credentials(self, client, db):
        _register_and_login(client)
        resp = client.post(
            "/api/tickets",
            json={"project_key": "TEST", "summary": "A ticket"},
        )
        assert resp.status_code == 404
        assert "Jira" in resp.get_json()["message"]


class TestCreateTicketWithSession:
    """POST /api/tickets -- with session auth and mocked Jira."""

    @patch("identityhub.services.jira_service.requests.request")
    def test_create_ticket_session_auth(self, mock_request, client, db, app):
        mock_request.side_effect = _mock_jira_create()

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.post(
            "/api/tickets",
            json={
                "project_key": "TEST",
                "summary": "Session ticket",
                "description": "Created via session",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["jira_key"] == "TEST-1"
        assert data["jira_id"] == "10001"
        assert data["project_key"] == "TEST"
        assert data["summary"] == "Session ticket"
        assert data["source"] == "web"

    @patch("identityhub.services.jira_service.requests.request")
    def test_create_ticket_uppercases_project_key(
        self, mock_request, client, db, app
    ):
        mock_request.side_effect = _mock_jira_create()

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.post(
            "/api/tickets",
            json={"project_key": "test", "summary": "Lowercased key"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["project_key"] == "TEST"


class TestCreateTicketWithApiKey:
    """POST /api/tickets -- with API key auth and mocked Jira."""

    @patch("identityhub.services.jira_service.requests.request")
    def test_create_ticket_api_key_auth(self, mock_request, client, db, app):
        mock_request.side_effect = _mock_jira_create()

        # Register user and get their info
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        # Generate an API key
        key_resp = client.post("/api/keys", json={"label": "test key"})
        assert key_resp.status_code == 201
        api_key = key_resp.get_json()["key"]

        # Logout to ensure we're testing API key auth, not session
        client.post("/api/auth/logout")

        resp = client.post(
            "/api/tickets",
            json={"project_key": "PROJ", "summary": "API key ticket"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["source"] == "api"
        assert data["jira_key"] == "TEST-1"


class TestListTickets:
    """GET /api/tickets -- served live from Jira (deletions reflected immediately)."""

    @patch("identityhub.services.jira_service.requests.request")
    def test_list_fetches_live_from_jira(self, mock_request, client, db, app):
        issues = [
            _jira_issue("TEST-2", "Second ticket", "TEST", "10002"),
            _jira_issue("TEST-1", "First ticket", "TEST", "10001"),
        ]
        mock_request.side_effect = _mock_jira(search_issues=issues)

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.get("/api/tickets?project_key=TEST")
        assert resp.status_code == 200
        tickets = resp.get_json()["tickets"]
        assert [t["jira_key"] for t in tickets] == ["TEST-2", "TEST-1"]
        assert tickets[0]["summary"] == "Second ticket"
        assert tickets[0]["project_key"] == "TEST"

    @patch("identityhub.services.jira_service.requests.request")
    def test_deleted_ticket_not_listed(self, mock_request, client, db, app):
        """Regression: a ticket deleted in Jira must not appear in Recent Tickets.

        Nothing is persisted locally, so once Jira no longer returns the issue
        (search returns nothing) the list is empty.
        """
        mock_request.side_effect = _mock_jira(search_issues=[])

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        create = client.post(
            "/api/tickets",
            json={"project_key": "TEST", "summary": "Soon to be deleted"},
        )
        assert create.status_code == 201

        # Jira no longer has the issue, and there is no local copy, so it is
        # not listed.
        resp = client.get("/api/tickets?project_key=TEST")
        assert resp.status_code == 200
        assert resp.get_json()["tickets"] == []

    @patch("identityhub.services.jira_service.requests.request")
    def test_list_builds_scoped_jql(self, mock_request, client, db, app):
        mock_request.side_effect = _mock_jira(search_issues=[])

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        client.get("/api/tickets?project_key=TEST")

        search_calls = [
            c for c in mock_request.call_args_list if "/search/jql" in c.args[1]
        ]
        assert search_calls, "expected a Jira search call"
        jql = search_calls[-1].kwargs["params"]["jql"]
        assert 'project = "TEST"' in jql
        assert "reporter = currentUser()" in jql
        assert "ORDER BY created DESC" in jql

    def test_list_no_credential_returns_empty(self, client, db):
        _register_and_login(client)
        resp = client.get("/api/tickets?project_key=TEST")
        assert resp.status_code == 200
        assert resp.get_json()["tickets"] == []
        assert resp.get_json()["unavailable"] is False

    def test_list_requires_auth(self, client, db):
        resp = client.get("/api/tickets")
        assert resp.status_code == 401

    @patch("identityhub.services.jira_service.requests.request")
    def test_list_unavailable_when_jira_down(self, mock_request, client, db, app):
        """Resilience: if Jira is unreachable, return an explicit unavailable
        state (empty list) rather than failing the dashboard."""
        mock_request.side_effect = requests.ConnectionError("boom")
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.get("/api/tickets?project_key=TEST")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["unavailable"] is True
        assert body["tickets"] == []

    @patch("identityhub.services.jira_service.requests.request")
    def test_list_surfaces_auth_error(self, mock_request, client, db, app):
        """A bad-credentials (401) failure is a real error, not an outage, so it
        must surface rather than silently falling back to the cache."""

        def bad_auth(method, url, **kwargs):
            resp = MagicMock()
            resp.status_code = 401
            resp.headers = {"Content-Type": "application/json"}
            resp.json.return_value = {"errorMessages": ["nope"]}
            return resp

        mock_request.side_effect = bad_auth
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.get("/api/tickets?project_key=TEST")
        assert resp.status_code == 502
        assert "authentication failed" in resp.get_json()["message"]
