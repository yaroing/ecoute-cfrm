import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("APP_ENV", "local") == "local"
SIMULATION = os.getenv("SIMULATION", "1" if DEBUG else "0") == "1"
if DEBUG:
    secret_file = BASE_DIR.parent / ".local-secrets.json"
    if not secret_file.exists():
        secret_file.write_text(
            json.dumps(
                {
                    k: secrets.token_hex(32)
                    for k in ["DJANGO_SECRET", "FIELD_KEY", "HMAC_KEY", "SMS_SECRET", "MESSAGING_SECRET"]
                }
            )
        )
    local = json.loads(secret_file.read_text())
else:
    local = {}


def secret(name):
    value = os.getenv(name, local.get(name))
    if not value:
        raise RuntimeError(f"Variable obligatoire : {name}")
    return value


SECRET_KEY = secret("DJANGO_SECRET")
FIELD_KEY = secret("FIELD_KEY")
HMAC_KEY = secret("HMAC_KEY")
WEBHOOK_SECRETS = {"sms": secret("SMS_SECRET"), "messagerie": secret("MESSAGING_SECRET")}
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_q",
    "core",
    "core.sensible",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "api.security.NoStoreMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "core.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
if os.getenv("POSTGRES_HOST"):
    shared = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "feedback"),
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": "5432",
    }
    DATABASES = {
        "default": {
            **shared,
            "USER": os.getenv("POSTGRES_USER", "feedback_app"),
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        },
        "sensible": {
            **shared,
            "USER": os.getenv("SENSITIVE_USER", "feedback_sensitive"),
            "PASSWORD": os.environ["SENSITIVE_PASSWORD"],
            "OPTIONS": {"options": "-c search_path=sensible"},
        },
    }
else:
    DATABASES = {
        name: {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / file, "OPTIONS": {"timeout": 30}}
        for name, file in [("default", "db.sqlite3"), ("sensible", "sensible.sqlite3")]
    }
DATABASE_ROUTERS = ["config.router.SensitiveRouter"]
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APPEND_SLASH = False
CORS_ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["api.security.AccessAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "api.security.problem_handler",
    "DEFAULT_THROTTLE_RATES": {"public": "20/min", "login": "20/min"},
}
SPECTACULAR_SETTINGS = {"TITLE": "CFRM – API de feedback", "VERSION": "1.0.0", "SERVE_INCLUDE_SCHEMA": False}
Q_CLUSTER = {"name": "feedback", "workers": 1, "timeout": 60, "retry": 90, "orm": "default"}
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
