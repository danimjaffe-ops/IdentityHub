"""Tests for the `flask nhi-digest` CLI command (identityhub/cli/digest.py).

The blog scrape, Claude summarization, and Jira issue creation are all mocked,
so the command's control flow (user lookup, credential guard, dry-run, ticket
creation) is exercised without any network access.
"""

from unittest.mock import MagicMock, patch

import pytest

from identityhub.cli.digest import nhi_digest
from identityhub.extensions import db
from identityhub.models.jira_credential import JiraCredential
from identityhub.models.user import User
from identityhub.services.crypto_service import encrypt


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user(email="digest@example.com", with_jira=False):
    user = User(email=email)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    if with_jira:
        db.session.add(
            JiraCredential(
                user_id=user.id,
                site_url="https://team.atlassian.net",
                email_encrypted=encrypt("jira@example.com"),
                api_token_encrypted=encrypt("token"),
            )
        )
        db.session.commit()
    return user


class TestNhiDigestCli:
    def test_unknown_user_exits_with_error(self, runner, db):
        result = runner.invoke(
            nhi_digest, ["--user-email", "nobody@example.com", "--project-key", "P"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_user_without_jira_credential_exits(self, runner, db):
        _make_user(with_jira=False)
        result = runner.invoke(
            nhi_digest, ["--user-email", "digest@example.com", "--project-key", "P"]
        )
        assert result.exit_code == 1
        assert "no Jira credentials" in result.output

    @patch("identityhub.services.jira_service.JiraService")
    @patch("identityhub.services.nhi_digest.summarize_with_claude")
    @patch("identityhub.services.nhi_digest.scrape_latest_post")
    def test_dry_run_does_not_create_ticket(
        self, mock_scrape, mock_summarize, mock_service_cls, runner, db
    ):
        _make_user(with_jira=True)
        mock_scrape.return_value = {
            "title": "Post",
            "url": "https://oasis.security/blog/post",
            "body_text": "body",
        }
        mock_summarize.return_value = "Summary text"

        result = runner.invoke(
            nhi_digest,
            [
                "--user-email",
                "digest@example.com",
                "--project-key",
                "P",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "Summary text" in result.output
        mock_service_cls.assert_not_called()

    @patch("identityhub.services.jira_service.JiraService")
    @patch("identityhub.services.nhi_digest.summarize_with_claude")
    @patch("identityhub.services.nhi_digest.scrape_latest_post")
    def test_success_creates_ticket(
        self, mock_scrape, mock_summarize, mock_service_cls, runner, db
    ):
        _make_user(with_jira=True)
        mock_scrape.return_value = {
            "title": "Big NHI Post",
            "url": "https://oasis.security/blog/big",
            "body_text": "body",
        }
        mock_summarize.return_value = "AI summary"
        service = MagicMock()
        service.create_issue.return_value = {"key": "P-42", "id": "10042"}
        mock_service_cls.return_value = service

        result = runner.invoke(
            nhi_digest,
            ["--user-email", "digest@example.com", "--project-key", "P"],
        )
        assert result.exit_code == 0
        assert "Created ticket: P-42" in result.output
        # The ticket summary/description are built from the scraped post + summary.
        args, _ = service.create_issue.call_args
        assert args[0] == "P"
        assert "Big NHI Post" in args[1]
        assert "AI summary" in args[2]
