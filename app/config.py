import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'stylo.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    ALLOW_NEGATIVE_STOCK = os.getenv("ALLOW_NEGATIVE_STOCK", "false").lower() == "true"
    WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "5511958438414")
    DEBUG = os.getenv("FLASK_ENV") == "development"

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
