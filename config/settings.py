import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


APP_ENV = os.environ.get("APP_ENV", "development")
if APP_ENV not in {"development", "production"}:
    raise RuntimeError(f"Invalid APP_ENV={APP_ENV!r}; must be 'development' or 'production'")
DEBUG = APP_ENV == "development"

SECRET_KEY = require_env("SECRET_KEY")

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

DATABASES = {
    "default": dj_database_url.parse(require_env("DATABASE_URL"), conn_max_age=600)
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "core",
    "candidates",
    "episodes",
    "ratings",
    "moderation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

MAIL_FROM = os.environ.get("MAIL_FROM", "No Agenda Talent Search <hello@noagendatalentsearch.com>")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
if RESEND_API_KEY:
    # Resend's SMTP relay: https://resend.com/docs/send-with-smtp
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    EMAIL_PORT = 587
    EMAIL_HOST_USER = "resend"
    EMAIL_HOST_PASSWORD = RESEND_API_KEY
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

RSS_FEED_URL = os.environ.get("RSS_FEED_URL", "https://feeds.noagendaassets.com/noagenda.xml")

SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days, sliding
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = APP_ENV == "production"
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = APP_ENV == "production"

LOGIN_URL = "accounts:request_link"
LOGIN_REDIRECT_URL = "core:home"
