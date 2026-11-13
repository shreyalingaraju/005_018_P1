"""Application configuration."""
import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
_SECRET_FILE = os.path.join(BASE_DIR, ".secret_key")


def _load_secret_key():
    """Use CNFR_SECRET_KEY if set, otherwise a random key persisted locally."""
    env = os.environ.get("CNFR_SECRET_KEY")
    if env:
        return env
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    with open(_SECRET_FILE, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


class Config:
    APP_NAME = "CAMPUS NETWATCH"
    APP_TAGLINE = "Intelligent Campus Network Monitoring & Complaint Management"
    SECRET_KEY = _load_secret_key()
    DATABASE = os.environ.get("CNFR_DATABASE", os.path.join(BASE_DIR, "database", "campus_network.db"))
    SEED_DEMO_COMPLAINTS = os.environ.get("CNFR_SEED_DEMO", "1") == "1"
    PASSWORD_HASH_METHOD = None  # werkzeug default (scrypt)

    CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("CNFR_SECURE_COOKIES", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 64 * 1024
    JSON_SORT_KEYS = False


class TestingConfig(Config):
    TESTING = True
    CSRF_ENABLED = False
    SEED_DEMO_COMPLAINTS = False
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"
