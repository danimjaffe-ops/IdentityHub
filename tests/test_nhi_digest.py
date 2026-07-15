"""Tests for the NHI digest service (identityhub/services/nhi_digest.py).

Both the blog scrape (``requests``) and the Claude summarization (Anthropic SDK)
are mocked, so these run offline and cost nothing.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from identityhub.services.nhi_digest import scrape_latest_post, summarize_with_claude


def _html_resp(text):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestScrapeLatestPost:
    @patch("identityhub.services.nhi_digest.requests.get")
    def test_extracts_title_url_and_body(self, mock_get):
        list_html = (
            "<html><body><article>"
            '<a href="/blog/nhi-trends">NHI Trends 2026</a>'
            "</article></body></html>"
        )
        post_html = (
            "<html><body><article><p>The real content.</p>"
            "<script>tracking()</script></article></body></html>"
        )
        mock_get.side_effect = [_html_resp(list_html), _html_resp(post_html)]

        post = scrape_latest_post()

        assert post["title"] == "NHI Trends 2026"
        assert post["url"] == "https://oasis.security/blog/nhi-trends"
        assert "The real content." in post["body_text"]
        # Script content must be stripped from the extracted body.
        assert "tracking()" not in post["body_text"]

    @patch("identityhub.services.nhi_digest.requests.get")
    def test_relative_href_is_absolutized(self, mock_get):
        list_html = '<article><a href="/blog/x">X</a></article>'
        mock_get.side_effect = [_html_resp(list_html), _html_resp("<article>y</article>")]
        assert scrape_latest_post()["url"].startswith("https://oasis.security/blog/")

    @patch("identityhub.services.nhi_digest.requests.get")
    def test_no_blog_links_raises(self, mock_get):
        mock_get.return_value = _html_resp('<html><body><a href="/about">About</a></body></html>')
        with pytest.raises(RuntimeError, match="Could not find any blog post links"):
            scrape_latest_post()

    @patch("identityhub.services.nhi_digest.requests.get")
    def test_post_fetch_failure_falls_back_to_title(self, mock_get):
        list_html = '<article><a href="/blog/x">Fallback Title</a></article>'
        mock_get.side_effect = [
            _html_resp(list_html),
            requests.RequestException("post page down"),
        ]
        post = scrape_latest_post()
        # When the post body can't be fetched, body_text falls back to the title.
        assert post["body_text"] == "Fallback Title"


class TestSummarizeWithClaude:
    @patch("identityhub.services.nhi_digest.anthropic.Anthropic")
    def test_returns_summary_text(self, mock_anthropic, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="A concise summary.")]
        )
        mock_anthropic.return_value = client

        result = summarize_with_claude("Title", "Body text")

        assert result == "A concise summary."
        _, kwargs = client.messages.create.call_args
        assert kwargs["model"] == "claude-sonnet-5"
        assert "Title" in kwargs["messages"][0]["content"]

    @patch("identityhub.services.nhi_digest.anthropic.Anthropic")
    def test_body_is_truncated_to_8000_chars(self, mock_anthropic, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="ok")]
        )
        mock_anthropic.return_value = client

        summarize_with_claude("T", "x" * 20000)
        prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "x" * 8000 in prompt
        assert "x" * 8001 not in prompt

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            summarize_with_claude("Title", "Body")
