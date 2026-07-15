import os
from datetime import timedelta


def _env_bool(name, default):
    """Read a boolean from the environment, tolerant of common spellings."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///identityhub.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FERNET_KEY = os.environ.get("FERNET_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Absolute session timeout: a login is valid for this long after it is
    # established, regardless of activity. Enforced server-side (see
    # identityhub/__init__.py) and mirrored onto the cookie's Max-Age.
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "8"))
    )
    # Do not slide the cookie expiry on every request — keep the timeout
    # absolute (from login) rather than idle-based.
    SESSION_REFRESH_EACH_REQUEST = False


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    FERNET_KEY = "x3r62Enja0C2ZW8Is6NDJTWO04CDvq95TEiWAWtSylU="


class E2ETestingConfig(TestingConfig):
    """Config for the Playwright E2E suite.

    The app is served by a background WSGI thread while the test process seeds
    and inspects the same database, so the DB is a file (not in-memory) and
    ``check_same_thread`` is relaxed to allow connections across threads.
    """

    SQLALCHEMY_DATABASE_URI = os.environ.get("E2E_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}


class ProductionConfig(Config):
    # Secure cookies by default in production. Overridable via env so the app
    # can run over plain HTTP for local/containerized QA — browsers refuse to
    # send Secure cookies over http://, which would silently break login.
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
