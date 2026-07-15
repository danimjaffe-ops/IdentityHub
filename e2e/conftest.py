"""Fixtures for the full-stack Playwright E2E suite.

A real WSGI server (the actual Flask app serving the built React SPA) runs in a
background thread; Playwright drives a browser against it. The only external
dependency — Jira — is stubbed at the ``requests`` layer, so the whole stack
(auth, sessions, SQLite, the SPA) is exercised end to end without a live Jira
account.

Run it with::

    make build            # or: cd frontend && npm run build
    .venv/bin/python -m pytest e2e/

These tests are NOT collected by a bare ``pytest`` run (see pytest.ini
``testpaths = tests``); invoke the ``e2e/`` path explicitly.
"""

import os
import socket
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.serving import make_server

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_INDEX = PROJECT_ROOT / "frontend" / "dist" / "index.html"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fake_jira(method, url, **kwargs):
    """Deterministic stand-in for the Jira REST endpoints the app calls."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    if "/myself" in url:
        resp.json.return_value = {"displayName": "E2E User"}
    elif "/project" in url:
        resp.json.return_value = [{"key": "NHI", "name": "NHI Findings", "id": "1"}]
    elif "/issue" in url:
        resp.json.return_value = {"key": "NHI-1", "id": "10001"}
    elif "/search/jql" in url:
        resp.json.return_value = {
            "issues": [
                {
                    "id": "10001",
                    "key": "NHI-1",
                    "fields": {
                        "summary": "Stale service account: svc-deploy-prod",
                        "created": "2026-07-15T09:00:00.000+0000",
                        "project": {"key": "NHI"},
                    },
                }
            ]
        }
    else:
        resp.json.return_value = {}
    return resp


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    if not DIST_INDEX.exists():
        pytest.skip(
            "frontend/dist not built — run `make build` (or "
            "`cd frontend && npm run build`) before the E2E suite"
        )

    # A file-backed SQLite DB shared between this process and the server thread.
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    os.environ["E2E_DATABASE_URL"] = f"sqlite:///{db_path}"

    patcher = patch(
        "identityhub.services.jira_service.requests.request", side_effect=_fake_jira
    )
    patcher.start()

    from identityhub import create_app
    from identityhub.extensions import db

    app = create_app("e2e")
    with app.app_context():
        db.create_all()

    port = _free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        patcher.stop()
        os.environ.pop("E2E_DATABASE_URL", None)
