import os
import sys
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

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudflare R2 (spec A.4). Like RESEND_API_KEY in Phase 1, this switches on the
# presence of credentials: with them the site stores uploads in R2 and serves
# them from the public media domain; without them it falls back to local disk so
# development works before the bucket exists. Nothing outside this block knows
# which is in play -- every upload path goes through `default_storage`.
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "")

USE_R2 = all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL])

if USE_R2:
    DEFAULT_FILE_STORAGE_CONFIG = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": R2_BUCKET,
            "access_key": R2_ACCESS_KEY_ID,
            "secret_key": R2_SECRET_ACCESS_KEY,
            "endpoint_url": f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            "region_name": "auto",
            # Reads go to the public custom domain, never to the S3 endpoint.
            "custom_domain": R2_PUBLIC_BASE_URL.split("//")[-1].rstrip("/"),
            # R2's public domain is unauthenticated, so signed query strings
            # would only produce URLs that expire for no benefit.
            "querystring_auth": False,
            # R2 has no ACL concept; sending one is an error, not a no-op.
            "default_acl": None,
            "file_overwrite": False,
            "signature_version": "s3v4",
            # Cloudflare documents the path-style endpoint form.
            "addressing_style": "path",
        },
    }
else:
    DEFAULT_FILE_STORAGE_CONFIG = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": DEFAULT_FILE_STORAGE_CONFIG,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")

# Uploads are validated in-request (fast -- ffprobe only reads headers) but
# transcoded in a background thread, which would otherwise race a test's own
# transaction rollback. `manage.py process_demos` is the backstop either way.
DEMO_PROCESS_IN_BACKGROUND = "test" not in sys.argv
DEMO_STALE_PROCESSING_MINUTES = 20

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

# Cloudflare and Render both terminate TLS and forward plain HTTP to gunicorn,
# so without this Django believes every request is http://. It then computes the
# expected CSRF origin as http://noagendatalentsearch.com, compares it with the
# https:// Origin the browser actually sent, and rejects the request -- a 403 on
# every POST, including the login form, on a site that otherwise looks healthy.
# Only trusted in production: the header is only meaningful when a proxy we
# control sets it, and a direct client could otherwise forge it.
if APP_ENV == "production":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_URL = "accounts:request_link"
LOGIN_REDIRECT_URL = "core:home"
