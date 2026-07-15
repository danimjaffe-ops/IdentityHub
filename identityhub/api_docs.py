"""Serve the OpenAPI spec and interactive Swagger UI.

The spec is a hand-maintained ``docs/openapi.yaml`` at the repo root (the single
source of truth). Swagger UI (assets vendored by ``flask-swagger-ui``, no CDN)
renders it at ``/api/docs`` and fetches the raw spec from ``/api/openapi.yaml``.

Both routes live under ``/api/*`` so they resolve before the SPA catch-all,
which only 404s *unmatched* ``/api/*`` paths.
"""

import os

from flask import send_file
from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = "/api/docs"
API_SPEC_URL = "/api/openapi.yaml"

_SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "docs", "openapi.yaml"
)


def register_api_docs(app):
    @app.route(API_SPEC_URL)
    def openapi_spec():
        return send_file(_SPEC_PATH, mimetype="application/yaml")

    swaggerui_bp = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_SPEC_URL,
        config={"app_name": "IdentityHub REST API"},
    )
    app.register_blueprint(swaggerui_bp, url_prefix=SWAGGER_URL)
