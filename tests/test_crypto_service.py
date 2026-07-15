"""Tests for the Fernet-based crypto service (identityhub/services/crypto_service.py).

These verify that Jira credentials are genuinely encrypted at rest and that a
missing key fails loudly rather than silently storing plaintext.
"""

import pytest

from identityhub.services.crypto_service import decrypt, encrypt


class TestRoundTrip:
    def test_encrypt_then_decrypt_returns_original(self, app):
        secret = "jira@example.com"
        assert decrypt(encrypt(secret)) == secret

    def test_encrypt_handles_unicode(self, app):
        secret = "pÄ$sw0rd—→✓"
        assert decrypt(encrypt(secret)) == secret

    def test_ciphertext_is_not_plaintext(self, app):
        """The stored bytes must not contain the plaintext (real encryption)."""
        secret = "super-secret-token"
        ciphertext = encrypt(secret)
        assert isinstance(ciphertext, bytes)
        assert secret.encode("utf-8") not in ciphertext

    def test_encrypt_is_non_deterministic(self, app):
        """Fernet embeds a random IV, so two encryptions differ but both decrypt."""
        secret = "same-input"
        a = encrypt(secret)
        b = encrypt(secret)
        assert a != b
        assert decrypt(a) == decrypt(b) == secret


class TestMissingKey:
    def test_encrypt_without_fernet_key_raises(self, app):
        app.config["FERNET_KEY"] = None
        with pytest.raises(RuntimeError, match="FERNET_KEY is not configured"):
            encrypt("anything")

    def test_decrypt_without_fernet_key_raises(self, app):
        app.config["FERNET_KEY"] = None
        with pytest.raises(RuntimeError, match="FERNET_KEY is not configured"):
            decrypt(b"anything")
