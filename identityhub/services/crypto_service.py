from cryptography.fernet import Fernet
from flask import current_app


def _get_fernet():
    key = current_app.config["FERNET_KEY"]
    if key is None:
        raise RuntimeError("FERNET_KEY is not configured")
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


def encrypt(plaintext: str) -> bytes:
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext).decode("utf-8")
