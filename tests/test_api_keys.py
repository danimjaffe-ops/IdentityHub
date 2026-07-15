"""Tests for the API keys blueprint (/api/keys)."""

from unittest.mock import MagicMock, patch

from identityhub.models.jira_credential import JiraCredential
from identityhub.services.crypto_service import encrypt


def _register_and_login(client):
    """Helper: register a user and return the response."""
    return client.post(
        "/api/auth/register",
        json={"email": "keyuser@example.com", "password": "password123"},
    )


def _mock_jira(search_issues=None):
    """Return a mock for requests.request that handles the Jira calls the app makes."""
    search_issues = search_issues or []
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "application/json"}

    def side_effect(method, url, **kwargs):
        mock_resp.status_code = 200
        if "/myself" in url:
            mock_resp.json.return_value = {"displayName": "Test User"}
        elif "/search/jql" in url:
            mock_resp.json.return_value = {"issues": search_issues}
        elif "/issue" in url:
            mock_resp.json.return_value = {"key": "TEST-1", "id": "10001"}
        return mock_resp

    return side_effect


class TestGenerateKey:
    """POST /api/keys"""

    def test_generate_key_success(self, client, db):
        _register_and_login(client)
        resp = client.post("/api/keys", json={"label": "My CI key"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "key" in data, "Full key should be returned on creation"
        assert data["key"].startswith("nhk_")
        assert data["key_prefix"] == data["key"][:12]
        assert data["label"] == "My CI key"
        assert data["is_active"] is True

    def test_generate_key_no_label(self, client, db):
        _register_and_login(client)
        resp = client.post("/api/keys", json={})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["label"] is None
        assert "key" in data

    def test_generate_key_label_too_long(self, client, db):
        _register_and_login(client)
        resp = client.post("/api/keys", json={"label": "x" * 101})
        assert resp.status_code == 400

    def test_generate_key_requires_session(self, client, db):
        resp = client.post("/api/keys", json={"label": "nope"})
        assert resp.status_code == 401


class TestListKeys:
    """GET /api/keys"""

    def test_list_keys(self, client, db):
        _register_and_login(client)
        client.post("/api/keys", json={"label": "key-1"})
        client.post("/api/keys", json={"label": "key-2"})

        resp = client.get("/api/keys")
        assert resp.status_code == 200
        keys = resp.get_json()["keys"]
        assert len(keys) == 2
        # Full key hash should NOT be exposed in list
        for k in keys:
            assert "key" not in k or not k.get("key", "").startswith("nhk_")
            assert "key_prefix" in k

    def test_list_keys_excludes_revoked(self, client, db):
        _register_and_login(client)
        resp1 = client.post("/api/keys", json={"label": "active"})
        resp2 = client.post("/api/keys", json={"label": "will-revoke"})
        revoke_id = resp2.get_json()["id"]
        client.delete(f"/api/keys/{revoke_id}")

        resp = client.get("/api/keys")
        keys = resp.get_json()["keys"]
        assert len(keys) == 1
        assert keys[0]["label"] == "active"

    def test_list_keys_requires_session(self, client, db):
        resp = client.get("/api/keys")
        assert resp.status_code == 401


class TestRevokeKey:
    """DELETE /api/keys/<id>"""

    def test_revoke_key(self, client, db):
        _register_and_login(client)
        key_resp = client.post("/api/keys", json={"label": "disposable"})
        key_id = key_resp.get_json()["id"]

        resp = client.delete(f"/api/keys/{key_id}")
        assert resp.status_code == 200
        assert "revoked" in resp.get_json()["message"].lower()

    def test_revoke_nonexistent_key(self, client, db):
        _register_and_login(client)
        resp = client.delete("/api/keys/99999")
        assert resp.status_code == 404

    def test_revoke_another_users_key(self, app, db):
        """Users cannot revoke keys they don't own."""
        client1 = app.test_client()
        client2 = app.test_client()

        client1.post(
            "/api/auth/register",
            json={"email": "owner@example.com", "password": "password123"},
        )
        key_resp = client1.post("/api/keys", json={"label": "owners key"})
        key_id = key_resp.get_json()["id"]

        client2.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        resp = client2.delete(f"/api/keys/{key_id}")
        assert resp.status_code == 404

    def test_revoke_requires_session(self, client, db):
        resp = client.delete("/api/keys/1")
        assert resp.status_code == 401


class TestRevokedKeyAuth:
    """Verify revoked API keys cannot authenticate."""

    @patch("identityhub.services.jira_service.requests.request")
    def test_revoked_key_cannot_authenticate(
        self, mock_request, client, db
    ):
        mock_request.side_effect = _mock_jira()

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()

        # Add Jira cred so ticket creation can proceed
        cred = JiraCredential(
            user_id=user_data["id"],
            site_url="https://test.atlassian.net",
            email_encrypted=encrypt("jira@example.com"),
            api_token_encrypted=encrypt("token123"),
        )
        db.session.add(cred)
        db.session.commit()

        # Generate and then revoke a key
        key_resp = client.post("/api/keys", json={"label": "temp"})
        api_key = key_resp.get_json()["key"]
        key_id = key_resp.get_json()["id"]
        client.delete(f"/api/keys/{key_id}")

        # Logout so session auth can't kick in
        client.post("/api/auth/logout")

        # Try using the revoked key
        resp = client.post(
            "/api/tickets",
            json={"project_key": "TEST", "summary": "Should fail"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 401


class TestApiKeyOnTickets:
    """Verify active API keys work for ticket endpoints."""

    @patch("identityhub.services.jira_service.requests.request")
    def test_api_key_creates_ticket(self, mock_request, client, db):
        mock_request.side_effect = _mock_jira()

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()

        cred = JiraCredential(
            user_id=user_data["id"],
            site_url="https://test.atlassian.net",
            email_encrypted=encrypt("jira@example.com"),
            api_token_encrypted=encrypt("token123"),
        )
        db.session.add(cred)
        db.session.commit()

        key_resp = client.post("/api/keys", json={"label": "ci"})
        api_key = key_resp.get_json()["key"]

        # Logout so only API key auth is used
        client.post("/api/auth/logout")

        resp = client.post(
            "/api/tickets",
            json={"project_key": "TEST", "summary": "Via API key"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201
        assert resp.get_json()["source"] == "api"

    @patch("identityhub.services.jira_service.requests.request")
    def test_api_key_lists_tickets(self, mock_request, client, db):
        # Tickets are listed live from Jira; the search returns one issue.
        mock_request.side_effect = _mock_jira(
            search_issues=[
                {
                    "id": "10001",
                    "key": "TEST-1",
                    "fields": {
                        "summary": "Live ticket",
                        "created": "2026-07-14T18:00:00.000+0000",
                        "project": {"key": "TEST"},
                    },
                }
            ]
        )

        _register_and_login(client)
        user_data = client.get("/api/auth/me").get_json()

        cred = JiraCredential(
            user_id=user_data["id"],
            site_url="https://test.atlassian.net",
            email_encrypted=encrypt("jira@example.com"),
            api_token_encrypted=encrypt("token123"),
        )
        db.session.add(cred)
        db.session.commit()

        # Generate API key and logout
        key_resp = client.post("/api/keys", json={})
        api_key = key_resp.get_json()["key"]
        client.post("/api/auth/logout")

        resp = client.get(
            "/api/tickets",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        tickets = resp.get_json()["tickets"]
        assert len(tickets) == 1
        assert tickets[0]["jira_key"] == "TEST-1"
