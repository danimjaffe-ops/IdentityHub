"""Tests for the Jira blueprint (/api/jira)."""

from unittest.mock import MagicMock, patch

from identityhub.models.jira_credential import JiraCredential
from identityhub.services.crypto_service import encrypt


def _register_and_login(client):
    """Helper: register a user and return the response."""
    return client.post(
        "/api/auth/register",
        json={"email": "jirauser@example.com", "password": "password123"},
    )


def _mock_jira_myself():
    """Mock that handles /myself endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {"displayName": "Test User"}
    return mock_resp


def _add_jira_credential(db, user_id):
    """Helper: add a Jira credential for the given user.

    Must be called while an app context is already active (e.g. via the db fixture).
    """
    cred = JiraCredential(
        user_id=user_id,
        site_url="https://myteam.atlassian.net",
        email_encrypted=encrypt("jira@example.com"),
        api_token_encrypted=encrypt("secret-token"),
    )
    db.session.add(cred)
    db.session.commit()
    return cred


class TestConnect:
    """POST /api/jira/credentials"""

    @patch("identityhub.services.jira_service.requests.request")
    def test_connect_success(self, mock_request, client, db):
        mock_request.return_value = _mock_jira_myself()

        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://myteam.atlassian.net",
                "email": "jira@example.com",
                "api_token": "secret-token",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["connected"] is True
        assert data["site_url"] == "https://myteam.atlassian.net"
        assert "email_masked" in data
        # Masked email should hide most of local part
        assert "@example.com" in data["email_masked"]

    @patch("identityhub.services.jira_service.requests.request")
    def test_connect_strips_trailing_slash(self, mock_request, client, db):
        mock_request.return_value = _mock_jira_myself()

        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://myteam.atlassian.net/",
                "email": "jira@example.com",
                "api_token": "secret-token",
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()["site_url"] == "https://myteam.atlassian.net"

    @patch("identityhub.services.jira_service.requests.request")
    def test_connect_replaces_existing(self, mock_request, client, db):
        mock_request.return_value = _mock_jira_myself()

        _register_and_login(client)
        # First connection
        client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://old.atlassian.net",
                "email": "old@example.com",
                "api_token": "old-token",
            },
        )
        # Replace with new
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://new.atlassian.net",
                "email": "new@example.com",
                "api_token": "new-token",
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()["site_url"] == "https://new.atlassian.net"

    def test_connect_missing_site_url(self, client, db):
        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={"email": "jira@example.com", "api_token": "token"},
        )
        assert resp.status_code == 400
        assert "URL" in resp.get_json()["message"]

    def test_connect_non_https_url(self, client, db):
        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "http://insecure.atlassian.net",
                "email": "jira@example.com",
                "api_token": "token",
            },
        )
        assert resp.status_code == 400
        assert "https" in resp.get_json()["message"].lower()

    def test_connect_missing_email(self, client, db):
        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://myteam.atlassian.net",
                "api_token": "token",
            },
        )
        assert resp.status_code == 400
        assert "email" in resp.get_json()["message"].lower()

    def test_connect_missing_api_token(self, client, db):
        _register_and_login(client)
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://myteam.atlassian.net",
                "email": "jira@example.com",
            },
        )
        assert resp.status_code == 400
        assert "token" in resp.get_json()["message"].lower()

    def test_connect_requires_session(self, client, db):
        resp = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://myteam.atlassian.net",
                "email": "jira@example.com",
                "api_token": "token",
            },
        )
        assert resp.status_code == 401


class TestStatus:
    """GET /api/jira/status"""

    def test_status_connected(self, client, db, app):
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.get("/api/jira/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is True
        assert data["site_url"] == "https://myteam.atlassian.net"
        assert "@example.com" in data["email_masked"]

    def test_status_not_connected(self, client, db):
        _register_and_login(client)
        resp = client.get("/api/jira/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False
        assert data["site_url"] is None

    def test_status_requires_session(self, client, db):
        resp = client.get("/api/jira/status")
        assert resp.status_code == 401


class TestDisconnect:
    """DELETE /api/jira/credentials"""

    def test_disconnect_success(self, client, db, app):
        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.delete("/api/jira/credentials")
        assert resp.status_code == 200
        assert "removed" in resp.get_json()["message"].lower()

        # Verify status is now disconnected
        status_resp = client.get("/api/jira/status")
        assert status_resp.get_json()["connected"] is False

    def test_disconnect_no_credentials(self, client, db):
        _register_and_login(client)
        resp = client.delete("/api/jira/credentials")
        assert resp.status_code == 404

    def test_disconnect_requires_session(self, client, db):
        resp = client.delete("/api/jira/credentials")
        assert resp.status_code == 401


class TestProjects:
    """GET /api/jira/projects"""

    @patch("identityhub.services.jira_service.requests.request")
    def test_list_projects(self, mock_request, client, db, app):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = [
            {"key": "PROJ", "name": "Project One", "id": "1"},
            {"key": "DEV", "name": "Development", "id": "2"},
        ]
        mock_request.return_value = mock_resp

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()
        _add_jira_credential(db, user_data["id"])

        resp = client.get("/api/jira/projects")
        assert resp.status_code == 200
        projects = resp.get_json()["projects"]
        assert len(projects) == 2
        assert projects[0]["key"] == "PROJ"
        assert projects[1]["key"] == "DEV"

    def test_projects_no_credentials(self, client, db):
        _register_and_login(client)
        resp = client.get("/api/jira/projects")
        assert resp.status_code == 404
        assert "Jira" in resp.get_json()["message"]

    def test_projects_requires_session(self, client, db):
        resp = client.get("/api/jira/projects")
        assert resp.status_code == 401
