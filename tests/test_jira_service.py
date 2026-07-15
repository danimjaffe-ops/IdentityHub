"""Unit tests for JiraService (identityhub/services/jira_service.py).

These exercise the service directly (not through the blueprint) so the error
mapping in ``_request`` and the request/response shaping in the higher-level
methods are covered independently of the HTTP layer above them.

Jira's network is mocked at ``requests.request`` exactly as the blueprint tests
do, so no live Jira account is required.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from identityhub.services.crypto_service import encrypt
from identityhub.services.jira_service import JiraService, _normalize_created
from identityhub.utils.errors import JiraError, JiraUnavailableError


@pytest.fixture
def service(app):
    """A JiraService backed by an in-memory (encrypted) credential.

    Built inside the app context (crypto needs FERNET_KEY) but not persisted —
    the service only reads ``site_url`` and the encrypted fields.
    """
    cred = SimpleNamespace(
        site_url="https://myteam.atlassian.net/",
        email_encrypted=encrypt("jira@example.com"),
        api_token_encrypted=encrypt("secret-token"),
    )
    return JiraService(cred)


def _resp(status=200, json_data=None, content_type="application/json", bad_json=False):
    m = MagicMock()
    m.status_code = status
    m.headers = {"Content-Type": content_type}
    if bad_json:
        m.json.side_effect = ValueError("no json")
    else:
        m.json.return_value = json_data
    return m


class TestInit:
    def test_strips_trailing_slash_from_base_url(self, service):
        assert service.base_url == "https://myteam.atlassian.net"


class TestRequestErrorMapping:
    """``_request`` maps HTTP/network failures onto the app's error types.

    ``AppError`` keeps its message on ``.message`` (not in ``str(exc)``), so we
    assert on that attribute rather than using pytest.raises(match=...).
    """

    @patch("identityhub.services.jira_service.requests.request")
    def test_401_raises_jira_error(self, mock_request, service):
        mock_request.return_value = _resp(status=401)
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "authentication failed" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_403_raises_jira_error(self, mock_request, service):
        mock_request.return_value = _resp(status=403)
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "access denied" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_500_raises_unavailable(self, mock_request, service):
        mock_request.return_value = _resp(status=500)
        with pytest.raises(JiraUnavailableError) as exc:
            service.test_connection()
        assert "HTTP 500" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_503_raises_unavailable(self, mock_request, service):
        mock_request.return_value = _resp(status=503)
        with pytest.raises(JiraUnavailableError):
            service.test_connection()

    @patch("identityhub.services.jira_service.requests.request")
    def test_connection_error_raises_unavailable(self, mock_request, service):
        mock_request.side_effect = requests.ConnectionError("boom")
        with pytest.raises(JiraUnavailableError) as exc:
            service.test_connection()
        assert "Cannot connect" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_timeout_raises_unavailable(self, mock_request, service):
        mock_request.side_effect = requests.Timeout("slow")
        with pytest.raises(JiraUnavailableError) as exc:
            service.test_connection()
        assert "timed out" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_4xx_with_error_messages_surfaces_them(self, mock_request, service):
        mock_request.return_value = _resp(
            status=400, json_data={"errorMessages": ["project is required", "bad"]}
        )
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "project is required; bad" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_4xx_with_unparseable_body_hints_site_url(self, mock_request, service):
        mock_request.return_value = _resp(status=404, bad_json=True)
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "Site URL" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_non_json_content_type_hints_site_url(self, mock_request, service):
        """A wrong Site URL often returns an HTML login page with a 200."""
        mock_request.return_value = _resp(content_type="text/html", json_data=None)
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "Site URL" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_json_content_type_but_invalid_body(self, mock_request, service):
        mock_request.return_value = _resp(bad_json=True)
        with pytest.raises(JiraError) as exc:
            service.test_connection()
        assert "invalid response" in exc.value.message

    @patch("identityhub.services.jira_service.requests.request")
    def test_builds_correct_url_and_auth(self, mock_request, service):
        mock_request.return_value = _resp(json_data={"displayName": "X"})
        service.test_connection()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert args[1] == "https://myteam.atlassian.net/rest/api/3/myself"
        assert kwargs["timeout"] == 15
        assert kwargs["auth"] is service.auth


class TestListProjects:
    @patch("identityhub.services.jira_service.requests.request")
    def test_shapes_projects(self, mock_request, service):
        mock_request.return_value = _resp(
            json_data=[
                {"key": "AAA", "name": "Alpha", "id": "1", "extra": "ignored"},
                {"key": "BBB", "name": "Beta", "id": "2"},
            ]
        )
        projects = service.list_projects()
        assert projects == [
            {"key": "AAA", "name": "Alpha", "id": "1"},
            {"key": "BBB", "name": "Beta", "id": "2"},
        ]


class TestCreateIssue:
    @patch("identityhub.services.jira_service.requests.request")
    def test_builds_adf_payload_and_returns_key(self, mock_request, service):
        mock_request.return_value = _resp(json_data={"key": "PROJ-7", "id": "10007"})

        result = service.create_issue("PROJ", "Fix the thing", "Details here")

        assert result == {"key": "PROJ-7", "id": "10007"}
        _, kwargs = mock_request.call_args
        fields = kwargs["json"]["fields"]
        assert fields["project"] == {"key": "PROJ"}
        assert fields["summary"] == "Fix the thing"
        assert fields["issuetype"] == {"name": "Task"}
        desc = fields["description"]
        assert desc["type"] == "doc"
        assert desc["content"][0]["content"][0]["text"] == "Details here"

    @patch("identityhub.services.jira_service.requests.request")
    def test_empty_description_produces_empty_text_node(self, mock_request, service):
        mock_request.return_value = _resp(json_data={"key": "P-1", "id": "1"})
        service.create_issue("P", "Summary only")
        _, kwargs = mock_request.call_args
        text = kwargs["json"]["fields"]["description"]["content"][0]["content"][0]["text"]
        assert text == ""

    @patch("identityhub.services.jira_service.requests.request")
    def test_custom_issue_type(self, mock_request, service):
        mock_request.return_value = _resp(json_data={"key": "P-1", "id": "1"})
        service.create_issue("P", "A bug", issue_type="Bug")
        _, kwargs = mock_request.call_args
        assert kwargs["json"]["fields"]["issuetype"] == {"name": "Bug"}


class TestSearchRecent:
    def _search_resp(self, issues):
        return _resp(json_data={"issues": issues})

    @patch("identityhub.services.jira_service.requests.request")
    def test_shapes_results_like_ticket_dict(self, mock_request, service):
        mock_request.return_value = self._search_resp(
            [
                {
                    "id": "10002",
                    "key": "TEST-2",
                    "fields": {
                        "summary": "Second",
                        "created": "2026-07-14T18:00:00.000+0000",
                        "project": {"key": "TEST"},
                    },
                }
            ]
        )
        results = service.search_recent(project_key="TEST")
        assert results == [
            {
                "id": 10002,
                "jira_key": "TEST-2",
                "jira_id": "10002",
                "project_key": "TEST",
                "summary": "Second",
                "description": None,
                "source": "jira",
                "created_at": "2026-07-14T18:00:00+00:00",
            }
        ]

    @patch("identityhub.services.jira_service.requests.request")
    def test_non_numeric_id_becomes_none(self, mock_request, service):
        mock_request.return_value = self._search_resp(
            [{"id": "abc", "key": "T-1", "fields": {"summary": "x", "project": {}}}]
        )
        assert service.search_recent()[0]["id"] is None

    @patch("identityhub.services.jira_service.requests.request")
    def test_missing_fields_are_tolerated(self, mock_request, service):
        mock_request.return_value = self._search_resp([{"id": "1", "key": "T-1"}])
        result = service.search_recent()[0]
        assert result["summary"] == ""
        assert result["created_at"] is None

    @patch("identityhub.services.jira_service.requests.request")
    def test_jql_scopes_to_reporter_and_project(self, mock_request, service):
        mock_request.return_value = self._search_resp([])
        service.search_recent(project_key="TEST")
        _, kwargs = mock_request.call_args
        jql = kwargs["params"]["jql"]
        assert 'project = "TEST"' in jql
        assert "reporter = currentUser()" in jql
        assert jql.endswith("ORDER BY created DESC")

    @patch("identityhub.services.jira_service.requests.request")
    def test_jql_without_project_omits_project_clause(self, mock_request, service):
        mock_request.return_value = self._search_resp([])
        service.search_recent()
        _, kwargs = mock_request.call_args
        assert "project =" not in kwargs["params"]["jql"]

    @patch("identityhub.services.jira_service.requests.request")
    def test_jql_escapes_quotes_in_project_key(self, mock_request, service):
        mock_request.return_value = self._search_resp([])
        service.search_recent(project_key='EVIL"KEY')
        _, kwargs = mock_request.call_args
        assert 'project = "EVIL\\"KEY"' in kwargs["params"]["jql"]

    @patch("identityhub.services.jira_service.requests.request")
    def test_limit_is_clamped(self, mock_request, service):
        mock_request.return_value = self._search_resp([])
        service.search_recent(limit=9999)
        assert mock_request.call_args.kwargs["params"]["maxResults"] == 100
        service.search_recent(limit=0)
        assert mock_request.call_args.kwargs["params"]["maxResults"] == 1


class TestNormalizeCreated:
    def test_valid_timestamp_gets_colon_offset(self):
        assert (
            _normalize_created("2026-07-14T18:00:00.000+0000")
            == "2026-07-14T18:00:00+00:00"
        )

    def test_malformed_returns_raw(self):
        assert _normalize_created("not-a-date") == "not-a-date"

    def test_none_returns_none(self):
        assert _normalize_created(None) is None

    def test_empty_string_returns_none(self):
        assert _normalize_created("") is None
