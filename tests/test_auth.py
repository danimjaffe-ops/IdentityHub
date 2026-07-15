"""Tests for the auth blueprint (/api/auth)."""

from datetime import datetime, timedelta, timezone


class TestRegister:
    """POST /api/auth/register"""

    def test_register_success(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "strongpass1",
                "confirm_password": "strongpass1",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["email"] == "new@example.com"
        assert "id" in data["user"]
        assert "created_at" in data["user"]

    def test_register_password_mismatch(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "mismatch@example.com",
                "password": "strongpass1",
                "confirm_password": "strongpass2",
            },
        )
        assert resp.status_code == 400
        assert "match" in resp.get_json()["message"].lower()
        # No account should have been created from a mismatched attempt.
        from identityhub.models.user import User

        assert User.query.filter_by(email="mismatch@example.com").first() is None

    def test_register_duplicate_email(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "password456"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["message"]

    def test_register_missing_email(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={"password": "password123"},
        )
        assert resp.status_code == 400
        assert "email" in resp.get_json()["message"].lower()

    def test_register_invalid_email(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={"email": "notanemail", "password": "password123"},
        )
        assert resp.status_code == 400

    def test_register_missing_password(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={"email": "x@example.com"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={"email": "x@example.com", "password": "short"},
        )
        assert resp.status_code == 400
        assert "8 characters" in resp.get_json()["message"]

    def test_register_empty_body(self, client, db):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 400

    def test_register_normalizes_email(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={"email": "  User@Example.COM  ", "password": "password123"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["email"] == "user@example.com"


class TestLogin:
    """POST /api/auth/login"""

    def test_login_success(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "user@example.com"

    def test_login_wrong_password(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["message"]

    def test_login_wrong_email(self, client, db):
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["message"]

    def test_login_missing_fields(self, client, db):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

        resp = client.post(
            "/api/auth/login", json={"email": "user@example.com"}
        )
        assert resp.status_code == 400

        resp = client.post(
            "/api/auth/login", json={"password": "password123"}
        )
        assert resp.status_code == 400

    def test_login_case_insensitive_email(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "USER@Example.COM", "password": "password123"},
        )
        assert resp.status_code == 200


class TestLogout:
    """POST /api/auth/logout"""

    def test_logout_success(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "logout@example.com", "password": "password123"},
        )
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert "Logged out" in resp.get_json()["message"]

    def test_logout_without_login(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_then_me_fails(self, client, db):
        # Register and login
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        # After register the user is logged in
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200

        client.post("/api/auth/logout")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestMe:
    """GET /api/auth/me"""

    def test_me_authenticated(self, client, db):
        client.post(
            "/api/auth/register",
            json={"email": "me@example.com", "password": "password123"},
        )
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "me@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_me_unauthenticated(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "authentication_required"


class TestSessionTimeout:
    """Absolute session timeout (PERMANENT_SESSION_LIFETIME)."""

    def _register(self, client, email="timeout@example.com"):
        client.post(
            "/api/auth/register",
            json={"email": email, "password": "password123"},
        )

    def test_login_records_start_time(self, client, db):
        """A fresh session carries an aware UTC start timestamp."""
        self._register(client)
        with client.session_transaction() as sess:
            assert "login_at" in sess
            started = datetime.fromisoformat(sess["login_at"])
            assert started.tzinfo is not None

    def test_session_valid_within_timeout(self, client, db):
        self._register(client)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200

    def test_session_just_under_timeout_still_valid(self, client, app, db):
        self._register(client)
        lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
        with client.session_transaction() as sess:
            sess["login_at"] = (
                datetime.now(timezone.utc) - lifetime + timedelta(minutes=5)
            ).isoformat()
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200

    def test_session_expires_after_absolute_timeout(self, client, app, db):
        self._register(client)
        lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
        # Backdate the session start just past the configured lifetime.
        with client.session_transaction() as sess:
            sess["login_at"] = (
                datetime.now(timezone.utc) - lifetime - timedelta(minutes=1)
            ).isoformat()
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "session_expired"

    def test_expired_timeout_is_independent_of_activity(self, client, app, db):
        """Repeated requests do not slide the deadline (absolute, not idle)."""
        self._register(client)
        lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
        with client.session_transaction() as sess:
            sess["login_at"] = (
                datetime.now(timezone.utc) - lifetime - timedelta(minutes=1)
            ).isoformat()
        # Even after making a request, the session stays expired.
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me").status_code == 401

    def test_session_without_start_time_is_expired(self, client, db):
        """A logged-in session missing the timestamp is treated as expired."""
        self._register(client)
        with client.session_transaction() as sess:
            sess.pop("login_at", None)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "session_expired"
