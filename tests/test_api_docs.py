"""Tests for the OpenAPI spec and Swagger UI docs routes."""

import os

import yaml

from identityhub.api_docs import _SPEC_PATH

_REPO_ROOT = os.path.dirname(os.path.dirname(_SPEC_PATH))


def test_openapi_spec_is_served_and_valid(client):
    resp = client.get("/api/openapi.yaml")
    assert resp.status_code == 200
    assert "yaml" in resp.headers["Content-Type"]

    spec = yaml.safe_load(resp.data)
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "IdentityHub REST API"


def test_swagger_ui_is_served(client):
    resp = client.get("/api/docs/")
    assert resp.status_code == 200
    assert b"swagger" in resp.data.lower()


def test_docs_routes_are_public(client):
    # Docs must be reachable without a session so users can read them first.
    assert client.get("/api/openapi.yaml").status_code == 200
    assert client.get("/api/docs/").status_code == 200


def test_spec_documents_every_registered_api_route(app):
    """The hand-maintained spec must stay in sync with the real routes."""
    with open(_SPEC_PATH) as f:
        spec = yaml.safe_load(f)
    documented = set(spec["paths"])

    live = set()
    for rule in app.url_map.iter_rules():
        path = rule.rule
        if not path.startswith("/api/"):
            continue
        if path in ("/api/openapi.yaml",) or path.startswith("/api/docs"):
            continue  # the docs machinery itself is not part of the REST surface
        # Normalize Flask converters (<int:key_id>) to OpenAPI style ({key_id}).
        normalized = path.replace("<int:key_id>", "{key_id}")
        live.add(normalized)

    missing = live - documented
    assert not missing, f"Undocumented API routes: {sorted(missing)}"


def test_spec_is_shipped_in_the_docker_image():
    """The spec is served at runtime, so it must reach the Docker image.

    Regression guard: ``.dockerignore`` excludes ``docs/`` wholesale, and the
    Dockerfile copies sources file-by-file. If the spec is either re-excluded or
    no longer copied, ``/api/docs`` 404s in the container even though every
    test-client test still passes. This can't be caught without inspecting the
    packaging, so we assert it directly.
    """
    with open(os.path.join(_REPO_ROOT, ".dockerignore")) as f:
        dockerignore = f.read()
    with open(os.path.join(_REPO_ROOT, "Dockerfile")) as f:
        dockerfile = f.read()

    # docs/ is excluded, so the spec must be explicitly re-included.
    assert "!docs/openapi.yaml" in dockerignore, (
        "docs/ is excluded by .dockerignore; re-include the spec with "
        "'!docs/openapi.yaml' or it won't be in the build context."
    )
    # ...and the Dockerfile must actually COPY it into the image.
    assert "docs/openapi.yaml" in dockerfile, (
        "Dockerfile must COPY docs/openapi.yaml so /api/docs works in the "
        "container."
    )
