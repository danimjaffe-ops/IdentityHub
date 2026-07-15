"""Smoke tests — fast, shallow checks that the app boots and the critical
happy path is wired end to end.

These are deliberately breadth-first, not depth-first: one assertion per step
that the pipe is alive (status codes, key fields), leaving deep behavior to the
focused unit/blueprint suites. Run just these as a quick gate:

    pytest -m smoke

Jira is the only external dependency, and it is faked here so the smoke suite
stays hermetic and offline.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.smoke


def _fake_jira(method, url, **kwargs):
    """Minimal stand-in for the Jira REST endpoints the app touches."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    if "/myself" in url:
        resp.json.return_value = {"displayName": "Smoke User"}
    elif "/project" in url:
        resp.json.return_value = [{"key": "SMOKE", "name": "Smoke", "id": "1"}]
    elif "/issue" in url:
        resp.json.return_value = {"key": "SMOKE-1", "id": "10001"}
    elif "/search/jql" in url:
        resp.json.return_value = {
            "issues": [
                {
                    "id": "10001",
                    "key": "SMOKE-1",
                    "fields": {
                        "summary": "Smoke ticket",
                        "created": "2026-07-15T09:00:00.000+0000",
                        "project": {"key": "SMOKE"},
                    },
                }
            ]
        }
    else:
        resp.json.return_value = {}
    return resp


class TestAppBoots:
    def test_unauthenticated_me_is_401(self, client):
        """The app is up and rejecting anonymous access to protected routes."""
        assert client.get("/api/auth/me").status_code == 401

    def test_unknown_api_route_is_404(self, client):
        assert client.get("/api/does-not-exist").status_code == 404


class TestCriticalPath:
    @patch("identityhub.services.jira_service.requests.request")
    def test_register_connect_create_list_key_logout(self, mock_request, client, db):
        mock_request.side_effect = _fake_jira

        # 1. Register (auto-logs-in).
        r = client.post(
            "/api/auth/register",
            json={"email": "smoke@example.com", "password": "password123"},
        )
        assert r.status_code == 201, r.get_json()

        # 2. Session is live.
        assert client.get("/api/auth/me").status_code == 200

        # 3. Connect Jira (validated against the faked /myself).
        r = client.post(
            "/api/jira/credentials",
            json={
                "site_url": "https://smoke.atlassian.net",
                "email": "jira@example.com",
                "api_token": "token",
            },
        )
        assert r.status_code == 201, r.get_json()
        assert client.get("/api/jira/status").get_json()["connected"] is True

        # 4. Projects load.
        assert client.get("/api/jira/projects").status_code == 200

        # 5. Create a ticket via the session.
        r = client.post(
            "/api/tickets",
            json={"project_key": "SMOKE", "summary": "Smoke ticket"},
        )
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["jira_key"] == "SMOKE-1"

        # 6. It shows up in the live-from-Jira recent list.
        r = client.get("/api/tickets?project_key=SMOKE")
        assert r.status_code == 200
        assert r.get_json()["tickets"], "expected the created ticket to be listed"

        # 7. Generate an API key and use it (no session).
        key = client.post("/api/keys", json={"label": "smoke"}).get_json()["key"]
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401  # session is gone
        r = client.post(
            "/api/tickets",
            json={"project_key": "SMOKE", "summary": "Via API key"},
            headers={"X-API-Key": key},
        )
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["source"] == "api"
