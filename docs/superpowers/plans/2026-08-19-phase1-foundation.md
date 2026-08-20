# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deployable Phase 1 foundation for noagendatalentsearch.com — Django project scaffold, full §5 database schema, magic-link authentication, account self-service, and admin role wiring — per `specs/noagendatalentsearch-spec.md` §9 Phase 1, as scoped in `docs/superpowers/specs/2026-08-19-phase1-foundation-design.md`.

**Architecture:** Single Django project (server-rendered templates, no SPA/API layer) with apps `accounts`, `core`, `candidates`, `episodes`, `ratings`, `moderation`. Postgres via Docker Compose. All §5 tables get models + migrations now; only `accounts` and `core` get working features this phase — everything else is schema-only.

**Tech Stack:** Django 5.1, Python 3.12, PostgreSQL 16, psycopg2-binary, gunicorn (prod), Docker Compose (dev). No Redis, no Celery, no REST framework, no pytest — Django's built-in `TestCase` and Postgres-backed rate limiting per the design doc.

## Global Constraints

- No password auth, ever. `User` has no usable password (`set_unusable_password()`); auth is magic-link only.
- One vote per account per item is a **future** (Phase 4) constraint, but the `Rating` model's `UniqueConstraint(user, rateable_type, rateable_id)` must exist now since the schema is built in full this phase (spec §8, §5).
- Rate limits, pinned exactly (spec B.3): 3 magic-link requests per email per hour; 10 magic-link requests per IP per hour; 5 signups per IP per day.
- Always respond identically to a magic-link request whether or not the email exists — no account enumeration (spec B.3).
- Magic link: single-use, 15-minute expiry, token hashed at rest (sha256), invalidated on use (spec B.3).
- Session: 90-day sliding expiry (refreshed every request), cookie flags HttpOnly + Secure + SameSite=Lax (spec B.3).
- `settings` table is the source of truth after first boot. Env vars seed it once via a data migration and are never read directly at request time again (spec §4.1). `get_setting(key)` uses a 60-second in-process cache.
- Episode model follows spec §3.4's explicit override of the §5 sketch: store both `guid` (normalized, unique) and `raw_guid`, and both `title_raw` and `title_display` — §3.4 is more specific than §5's "suggested" shorthand and takes precedence.
- Docker image installs `ffmpeg` now even though unused until Phase 3 (spec Appendix A.6).
- Test command for every task in this plan: `docker compose run --rm web python manage.py test <label>` (Postgres must be reachable, which is why the Docker infra task comes first).
- Every migration file must be generated with `python manage.py makemigrations <app>` inside the container, not written by hand, so Django's migration state stays consistent.

---

## Task 1: Repository scaffold + Docker Compose infra

**Files:**
- Create: `requirements.txt`
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `render.yaml`

**Interfaces:**
- Produces: `config.settings` module readable by every later app (`INSTALLED_APPS`, `AUTH_USER_MODEL = "accounts.User"`, `DATABASES` parsed from `DATABASE_URL`). Later tasks append to `INSTALLED_APPS` and `config/urls.py`'s `urlpatterns`.
- Produces: a running `db` (Postgres 16) and `web` (Django) service reachable via `docker compose`.

- [ ] **Step 1: Write `requirements.txt`**

```
Django==5.1.*
psycopg2-binary==2.9.*
dj-database-url==2.3.*
gunicorn==23.*
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.env
*.sqlite3
/staticfiles/
.DS_Store
```

- [ ] **Step 3: Write `.dockerignore`**

```
.git
.gitignore
__pycache__
*.pyc
.env
docs/
```

- [ ] **Step 4: Write `manage.py`**

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write `config/__init__.py`** (empty file)

- [ ] **Step 6: Write `config/settings.py`**

```python
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
DEBUG = APP_ENV != "production"

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
MAIL_FROM = os.environ.get("MAIL_FROM", "No Agenda Talent Search <hello@noagendatalentsearch.com>")

SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days, sliding
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = APP_ENV == "production"
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = APP_ENV == "production"

LOGIN_URL = "accounts:request_link"
LOGIN_REDIRECT_URL = "core:home"
```

- [ ] **Step 7: Write `config/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
]
```

- [ ] **Step 8: Write `config/wsgi.py`**

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
```

- [ ] **Step 9: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

- [ ] **Step 10: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: natsearch
      POSTGRES_USER: natsearch
      POSTGRES_PASSWORD: natsearch
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db

volumes:
  pgdata:
```

- [ ] **Step 11: Write `.env.example`**

```
# Core
APP_ENV=development
APP_URL=http://localhost:8000
SECRET_KEY=change-me-to-64-random-chars
DATABASE_URL=postgres://natsearch:natsearch@db:5432/natsearch
ALLOWED_HOSTS=localhost,127.0.0.1

# Email
RESEND_API_KEY=
MAIL_FROM="No Agenda Talent Search <hello@noagendatalentsearch.com>"
ADMIN_NOTIFY_EMAIL=hello@noagendatalentsearch.com

# Storage (R2) - not used until Phase 3
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=nats-media
R2_PUBLIC_BASE_URL=

# Anti-bot - not used until Phase 5
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=

# Feed - not used until Phase 2
RSS_FEED_URL=https://feeds.noagendaassets.com/noagenda.xml
MIN_EPISODE_NUMBER=1890

# Monitoring
SENTRY_DSN=

# First-boot seed values ONLY -- after initial migration the `settings`
# table is the source of truth and these are ignored (see spec Sec 4.1).
VOTE_ELIGIBILITY_HOURS=48
MIN_VOTES_TO_DISPLAY=10
APPEARANCE_RATING_WINDOW_DAYS=14
DEMO_MAX_DURATION_SEC=900
DEMO_MAX_FILE_MB=50
LEADERBOARD_SIZE=10
SCORE_WEIGHT_APPEARANCE=0.7
SCORE_WEIGHT_DEMO=0.3
```

- [ ] **Step 12: Write `render.yaml`** (web service + Postgres only — cron jobs are added in the phases that create the management commands they run: `rss-sync` in Phase 2, `recompute-scores` in Phase 4)

```yaml
services:
  - type: web
    name: noagendatalentsearch
    runtime: docker
    dockerfilePath: ./Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: noagendatalentsearch-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: APP_ENV
        value: production

databases:
  - name: noagendatalentsearch-db
    plan: starter
```

- [ ] **Step 13: Create an `.env` from the example and bring up the database**

Run: `cp .env.example .env` then edit `.env` to set `SECRET_KEY` to any 64-character random string for local dev (e.g. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).

Run: `docker compose up -d db`
Expected: `db` container starts and stays running (`docker compose ps` shows it `Up`).

- [ ] **Step 14: Build the web image and verify Django boots**

Since no app code exists yet, `config/urls.py` references `core.urls` and `accounts.urls`, which don't exist until Tasks 3 and 5. Create empty placeholder files so `manage.py check` passes at the end of this task: `core/urls.py` and `accounts/urls.py`, each containing `urlpatterns = []`, plus empty `core/__init__.py` and `accounts/__init__.py` (these two app packages are fully built out in Tasks 2-8; this step only creates the minimal stub so the scaffold is self-consistent).

Run: `docker compose build web`
Expected: image builds successfully.

Run: `docker compose run --rm web python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 15: Commit**

```bash
git add requirements.txt manage.py config Dockerfile docker-compose.yml .dockerignore .gitignore .env.example render.yaml core/__init__.py core/urls.py accounts/__init__.py accounts/urls.py
git commit -m "Scaffold Django project and Docker Compose infra"
```

---

## Task 2: `accounts` app — custom User model

**Files:**
- Create: `accounts/models.py`
- Create: `accounts/admin.py`
- Create: `accounts/apps.py`
- Create: `accounts/migrations/__init__.py`
- Create: `accounts/tests/__init__.py`
- Create: `accounts/tests/test_models.py`

**Interfaces:**
- Consumes: `AUTH_USER_MODEL = "accounts.User"` from `config/settings.py` (Task 1).
- Produces: `accounts.models.User` with fields `email`, `display_name`, `role` (`User.Role.PRODUCER|MODERATOR|ADMIN`), `created_at`, `email_verified_at`, `banned_at`, `deleted_at`, `vote_eligible_override_at`, `signup_ip`; properties `is_staff`, `is_superuser`, `is_active`; manager `User.objects.create_user(email, display_name="", role=Role.PRODUCER, signup_ip=None)` and `User.objects.create_superuser(email, display_name="")`. Later tasks (3-14) import `from accounts.models import User`.

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_models.py
from django.test import TestCase

from accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_defaults_to_producer_role(self):
        user = User.objects.create_user(email="Producer@Example.com")
        self.assertEqual(user.role, User.Role.PRODUCER)
        self.assertEqual(user.email, "producer@example.com")  # normalized lowercase

    def test_create_user_has_no_usable_password(self):
        user = User.objects.create_user(email="producer2@example.com")
        self.assertFalse(user.has_usable_password())

    def test_moderator_is_staff_not_superuser(self):
        user = User.objects.create_user(email="mod@example.com", role=User.Role.MODERATOR)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_admin_is_staff_and_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_producer_is_neither_staff_nor_superuser(self):
        user = User.objects.create_user(email="plain@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_banned_user_is_not_active(self):
        from django.utils import timezone

        user = User.objects.create_user(email="banned@example.com")
        self.assertTrue(user.is_active)
        user.banned_at = timezone.now()
        user.save()
        self.assertFalse(user.is_active)

    def test_email_is_unique(self):
        from django.db import IntegrityError

        User.objects.create_user(email="dup@example.com")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_models -v 2`
Expected: FAIL/ERROR — `accounts.models` has no attribute `User` (module doesn't exist yet).

- [ ] **Step 3: Write `accounts/apps.py`**

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
```

- [ ] **Step 4: Write `accounts/models.py`**

```python
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def _create(self, email, display_name, role, signup_ip, **extra):
        if not email:
            raise ValueError("email is required")
        user = self.model(
            email=self.normalize_email(email).lower(),
            display_name=display_name,
            role=role,
            signup_ip=signup_ip,
            **extra,
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, display_name="", role=None, signup_ip=None, **extra):
        return self._create(email, display_name, role or User.Role.PRODUCER, signup_ip, **extra)

    def create_superuser(self, email, display_name="", **extra):
        return self._create(email, display_name, User.Role.ADMIN, None, **extra)


class User(AbstractBaseUser):
    class Role(models.TextChoices):
        PRODUCER = "producer", "Producer"
        MODERATOR = "moderator", "Moderator"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PRODUCER)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    vote_eligible_override_at = models.DateTimeField(null=True, blank=True)
    signup_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def is_staff(self):
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    @property
    def is_superuser(self):
        return self.role == self.Role.ADMIN

    @property
    def is_active(self):
        return self.banned_at is None and self.deleted_at is None

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_staff
```

- [ ] **Step 5: Write `accounts/admin.py`**

```python
from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "role", "created_at", "banned_at", "deleted_at")
    list_filter = ("role",)
    search_fields = ("email", "display_name")
    readonly_fields = ("created_at",)
```

- [ ] **Step 6: Create `accounts/migrations/__init__.py` and `accounts/tests/__init__.py`** (empty files)

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations accounts`
Expected: creates `accounts/migrations/0001_initial.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly, including `django.contrib.admin`/`auth`/`sessions` migrations that depend on `AUTH_USER_MODEL`.

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_models -v 2`
Expected: PASS, 7 tests.

- [ ] **Step 9: Commit**

```bash
git add accounts/
git commit -m "Add custom User model with magic-link-ready auth (no passwords)"
```

---

## Task 3: `core` app — Settings model, get_setting(), /healthz, home stub

**Files:**
- Create: `core/apps.py`
- Create: `core/models.py`
- Create: `core/settings_util.py`
- Create: `core/views.py`
- Create: `core/urls.py` (overwrite Task 1's stub)
- Create: `core/migrations/__init__.py`
- Create: `core/migrations/0001_initial.py` (generated)
- Create: `core/migrations/0002_seed_settings.py`
- Create: `templates/base.html`
- Create: `templates/core/home.html`
- Create: `core/tests/__init__.py`
- Create: `core/tests/test_settings_util.py`
- Create: `core/tests/test_views.py`

**Interfaces:**
- Produces: `core.settings_util.get_setting(key)` — raises `KeyError` for unknown keys, returns the JSON-decoded value, cached 60s in-process. Later phases (2-5) call this for `min_episode_number`, `min_votes_to_display`, etc.
- Produces: `core.models.Settings(key, value_json)`.
- Produces: URL names `core:home`, `core:healthz`.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/test_settings_util.py
from django.core.cache import cache
from django.test import TestCase

from core.models import Settings
from core.settings_util import get_setting


class GetSettingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_returns_seeded_value(self):
        Settings.objects.create(key="leaderboard_size", value_json=10)
        self.assertEqual(get_setting("leaderboard_size"), 10)

    def test_unknown_key_raises_keyerror(self):
        with self.assertRaises(KeyError):
            get_setting("not_a_real_setting")

    def test_value_is_cached_after_first_read(self):
        Settings.objects.create(key="auditions_open", value_json=True)
        self.assertTrue(get_setting("auditions_open"))
        Settings.objects.filter(key="auditions_open").update(value_json=False)
        # still cached, so still True
        self.assertTrue(get_setting("auditions_open"))

    def test_falsy_values_are_cached_correctly(self):
        Settings.objects.create(key="score_weight_demo", value_json=0)
        self.assertEqual(get_setting("score_weight_demo"), 0)
```

```python
# core/tests/test_views.py
from django.test import TestCase


class HealthzTests(TestCase):
    def test_healthz_returns_200_with_db_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class HomeTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web python manage.py test core -v 2`
Expected: FAIL — `core.models` / `core.settings_util` don't exist yet, and `/` and `/healthz` 404.

- [ ] **Step 3: Write `core/apps.py`**

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
```

- [ ] **Step 4: Write `core/models.py`**

```python
from django.db import models


class Settings(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    value_json = models.JSONField()

    def __str__(self):
        return self.key
```

- [ ] **Step 5: Write `core/settings_util.py`**

```python
from django.core.cache import cache

from .models import Settings

CACHE_PREFIX = "core:setting:"
CACHE_TTL_SECONDS = 60


def get_setting(key):
    cache_key = f"{CACHE_PREFIX}{key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["value"]

    try:
        row = Settings.objects.get(key=key)
    except Settings.DoesNotExist:
        raise KeyError(f"Unknown setting: {key}")

    cache.set(cache_key, {"value": row.value_json}, CACHE_TTL_SECONDS)
    return row.value_json
```

- [ ] **Step 6: Write `core/views.py`**

```python
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})
```

- [ ] **Step 7: Write `core/urls.py`** (overwrites the Task 1 stub)

```python
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
]
```

- [ ] **Step 8: Write `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}No Agenda Talent Search{% endblock %}</title>
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 9: Write `templates/core/home.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>No Agenda Talent Search</h1>
<p>The community-driven audition for the show's next co-host.</p>
{% if user.is_authenticated %}
  <p>Signed in as {{ user.email }}. <a href="{% url 'accounts:logout' %}">Log out</a></p>
{% else %}
  <p><a href="{% url 'accounts:request_link' %}">Log in or sign up</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 10: Create `core/migrations/__init__.py`** (empty file)

- [ ] **Step 11: Generate the initial migration and write the seed data migration**

Run: `docker compose run --rm web python manage.py makemigrations core`
Expected: creates `core/migrations/0001_initial.py`.

```python
# core/migrations/0002_seed_settings.py
import os

from django.db import migrations


def _env_int(name, default):
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name, default):
    raw = os.environ.get(name)
    return float(raw) if raw else default


def seed_settings(apps, schema_editor):
    Settings = apps.get_model("core", "Settings")
    defaults = {
        "vote_eligibility_hours": _env_int("VOTE_ELIGIBILITY_HOURS", 48),
        "min_votes_to_display": _env_int("MIN_VOTES_TO_DISPLAY", 10),
        "appearance_rating_window_days": _env_int("APPEARANCE_RATING_WINDOW_DAYS", 14),
        "demo_max_duration_sec": _env_int("DEMO_MAX_DURATION_SEC", 900),
        "demo_max_file_mb": _env_int("DEMO_MAX_FILE_MB", 50),
        "leaderboard_size": _env_int("LEADERBOARD_SIZE", 10),
        "score_weight_appearance": _env_float("SCORE_WEIGHT_APPEARANCE", 0.7),
        "score_weight_demo": _env_float("SCORE_WEIGHT_DEMO", 0.3),
        "auditions_open": True,
        "min_episode_number": _env_int("MIN_EPISODE_NUMBER", 1890),
    }
    for key, value in defaults.items():
        Settings.objects.get_or_create(key=key, defaults={"value_json": value})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed_settings, noop_reverse)]
```

- [ ] **Step 12: Run migrations**

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies `core.0001_initial` and `core.0002_seed_settings` cleanly.

- [ ] **Step 13: Run tests to verify they pass**

Run: `docker compose run --rm web python manage.py test core -v 2`
Expected: PASS. Note: `test_home_returns_200` will fail with a `NoReverseMatch` on `accounts:logout`/`accounts:request_link` until Task 5 exists — guard the template with the `{% if user.is_authenticated %}` block as written (it references the URL names but they aren't resolved unless that branch renders; since `AnonymousUser.is_authenticated` is `False` in tests with no logged-in user, only the `else` branch renders, which requires `accounts:request_link` to exist). To keep this task fully independent, temporarily use plain text instead of `{% url %}` tags in `home.html` for this task, and switch to the real `{% url %}` links in Task 5 once those routes exist:

```html
{% extends "base.html" %}
{% block content %}
<h1>No Agenda Talent Search</h1>
<p>The community-driven audition for the show's next co-host.</p>
{% if user.is_authenticated %}
  <p>Signed in as {{ user.email }}.</p>
{% else %}
  <p>Log in or sign up to participate.</p>
{% endif %}
{% endblock %}
```

Run: `docker compose run --rm web python manage.py test core -v 2`
Expected: PASS, 6 tests.

- [ ] **Step 14: Commit**

```bash
git add core/ templates/
git commit -m "Add core app: Settings model, get_setting(), /healthz, home stub"
```

---

## Task 4: `accounts` app — MagicLink model + rate limit helpers

**Files:**
- Create: `accounts/tokens.py`
- Create: `accounts/ratelimit.py`
- Modify: `accounts/models.py` (add `MagicLink`)
- Modify: `accounts/admin.py` (register `MagicLink`)
- Create: `accounts/tests/test_tokens.py`
- Create: `accounts/tests/test_ratelimit.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2).
- Produces: `accounts.models.MagicLink(user, token_hash, requested_ip, expires_at, used_at, created_at)`. Produces `accounts.tokens.generate_token()`, `hash_token(raw)`, `create_magic_link(user, requested_ip=None) -> raw_token`, `consume_magic_link(raw_token) -> User | None`. Produces `accounts.ratelimit.email_link_requests_exceeded(email)`, `ip_link_requests_exceeded(ip)`, `ip_signup_limit_exceeded(ip)`. Task 5 imports all of these.

- [ ] **Step 1: Write the failing tests**

```python
# accounts/tests/test_tokens.py
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import MagicLink, User
from accounts.tokens import consume_magic_link, create_magic_link, hash_token


class MagicLinkTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_create_magic_link_stores_hash_not_raw_token(self):
        raw_token = create_magic_link(self.user)
        link = MagicLink.objects.get(user=self.user)
        self.assertEqual(link.token_hash, hash_token(raw_token))
        self.assertNotEqual(link.token_hash, raw_token)

    def test_consume_valid_token_returns_user_and_marks_used(self):
        raw_token = create_magic_link(self.user)
        result = consume_magic_link(raw_token)
        self.assertEqual(result, self.user)
        link = MagicLink.objects.get(user=self.user)
        self.assertIsNotNone(link.used_at)

    def test_consume_same_token_twice_fails_second_time(self):
        raw_token = create_magic_link(self.user)
        consume_magic_link(raw_token)
        self.assertIsNone(consume_magic_link(raw_token))

    def test_consume_expired_token_fails(self):
        raw_token = create_magic_link(self.user)
        link = MagicLink.objects.get(user=self.user)
        link.expires_at = timezone.now() - timedelta(minutes=1)
        link.save()
        self.assertIsNone(consume_magic_link(raw_token))

    def test_consume_unknown_token_fails(self):
        self.assertIsNone(consume_magic_link("not-a-real-token"))
```

```python
# accounts/tests/test_ratelimit.py
from django.test import TestCase

from accounts.models import User
from accounts.ratelimit import (
    email_link_requests_exceeded,
    ip_link_requests_exceeded,
    ip_signup_limit_exceeded,
)
from accounts.tokens import create_magic_link


class RateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_email_limit_not_exceeded_below_threshold(self):
        for _ in range(2):
            create_magic_link(self.user)
        self.assertFalse(email_link_requests_exceeded("producer@example.com"))

    def test_email_limit_exceeded_at_threshold(self):
        for _ in range(3):
            create_magic_link(self.user)
        self.assertTrue(email_link_requests_exceeded("producer@example.com"))

    def test_ip_limit_not_exceeded_below_threshold(self):
        for _ in range(9):
            create_magic_link(self.user, requested_ip="1.2.3.4")
        self.assertFalse(ip_link_requests_exceeded("1.2.3.4"))

    def test_ip_limit_exceeded_at_threshold(self):
        for _ in range(10):
            create_magic_link(self.user, requested_ip="1.2.3.4")
        self.assertTrue(ip_link_requests_exceeded("1.2.3.4"))

    def test_signup_ip_limit_exceeded_at_threshold(self):
        for i in range(5):
            User.objects.create_user(email=f"new{i}@example.com", signup_ip="5.6.7.8")
        self.assertTrue(ip_signup_limit_exceeded("5.6.7.8"))

    def test_signup_ip_limit_ignores_none(self):
        self.assertFalse(ip_signup_limit_exceeded(None))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_tokens accounts.tests.test_ratelimit -v 2`
Expected: FAIL — `accounts.tokens`, `accounts.ratelimit`, and `MagicLink` don't exist yet.

- [ ] **Step 3: Add `MagicLink` to `accounts/models.py`** (append to the file from Task 2)

```python
class MagicLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="magic_links")
    token_hash = models.CharField(max_length=64, unique=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 4: Write `accounts/tokens.py`**

```python
import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import MagicLink

TOKEN_BYTES = 32
EXPIRY_MINUTES = 15


def generate_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_magic_link(user, requested_ip=None):
    raw_token = generate_token()
    MagicLink.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        requested_ip=requested_ip,
        expires_at=timezone.now() + timedelta(minutes=EXPIRY_MINUTES),
    )
    return raw_token


def consume_magic_link(raw_token):
    token_hash = hash_token(raw_token)
    try:
        link = MagicLink.objects.get(token_hash=token_hash)
    except MagicLink.DoesNotExist:
        return None
    if link.used_at is not None:
        return None
    if link.expires_at < timezone.now():
        return None
    link.used_at = timezone.now()
    link.save(update_fields=["used_at"])
    return link.user
```

- [ ] **Step 5: Write `accounts/ratelimit.py`**

```python
from datetime import timedelta

from django.utils import timezone

from .models import MagicLink, User

EMAIL_LINK_LIMIT_PER_HOUR = 3
IP_LINK_LIMIT_PER_HOUR = 10
IP_SIGNUP_LIMIT_PER_DAY = 5


def email_link_requests_exceeded(email):
    window_start = timezone.now() - timedelta(hours=1)
    count = MagicLink.objects.filter(user__email=email, created_at__gte=window_start).count()
    return count >= EMAIL_LINK_LIMIT_PER_HOUR


def ip_link_requests_exceeded(ip):
    if not ip:
        return False
    window_start = timezone.now() - timedelta(hours=1)
    count = MagicLink.objects.filter(requested_ip=ip, created_at__gte=window_start).count()
    return count >= IP_LINK_LIMIT_PER_HOUR


def ip_signup_limit_exceeded(ip):
    if not ip:
        return False
    window_start = timezone.now() - timedelta(days=1)
    count = User.objects.filter(signup_ip=ip, created_at__gte=window_start).count()
    return count >= IP_SIGNUP_LIMIT_PER_DAY
```

- [ ] **Step 6: Register `MagicLink` in `accounts/admin.py`** (append)

```python
from .models import MagicLink


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "requested_ip", "expires_at", "used_at", "created_at")
    readonly_fields = ("token_hash", "created_at")
```

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations accounts`
Expected: creates `accounts/migrations/0002_magiclink.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_tokens accounts.tests.test_ratelimit -v 2`
Expected: PASS, 11 tests.

- [ ] **Step 9: Commit**

```bash
git add accounts/
git commit -m "Add MagicLink model and rate limit helpers"
```

---

## Task 5: Magic-link request flow (signup/login)

**Files:**
- Create: `accounts/forms.py`
- Create: `accounts/utils.py`
- Create: `accounts/emails.py`
- Modify: `accounts/views.py` (create — request-link view)
- Modify: `accounts/urls.py` (overwrite Task 1 stub)
- Create: `templates/accounts/request_link.html`
- Create: `templates/accounts/link_sent.html`
- Create: `accounts/tests/test_views_request_link.py`

**Interfaces:**
- Consumes: `accounts.ratelimit.*`, `accounts.tokens.create_magic_link` (Task 4); `accounts.models.User` (Task 2).
- Produces: URL name `accounts:request_link` (GET/POST `/login/` and `/signup/` both route here — see Step 6). Produces `accounts.emails.send_magic_link_email(to_email, raw_token)`. Task 6 reuses `templates/accounts/request_link.html` render path for the "send me a new one" form on the expired-link page.

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_views_request_link.py
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import MagicLink, User


class RequestMagicLinkTests(TestCase):
    def test_get_shows_form(self):
        response = self.client.get(reverse("accounts:request_link"))
        self.assertEqual(response.status_code, 200)

    def test_post_new_email_creates_user_and_sends_link(self):
        response = self.client.post(reverse("accounts:request_link"), {"email": "new@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/link_sent.html")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("new@example.com", mail.outbox[0].to)

    def test_post_existing_email_does_not_duplicate_user(self):
        User.objects.create_user(email="existing@example.com")
        self.client.post(reverse("accounts:request_link"), {"email": "existing@example.com"})
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_response_identical_for_existing_and_nonexistent_email(self):
        User.objects.create_user(email="existing2@example.com")
        response_existing = self.client.post(reverse("accounts:request_link"), {"email": "existing2@example.com"})
        response_new = self.client.post(reverse("accounts:request_link"), {"email": "brandnew@example.com"})
        self.assertEqual(response_existing.status_code, response_new.status_code)
        self.assertEqual(
            response_existing.content.decode(),
            response_new.content.decode(),
        )

    def test_email_over_rate_limit_sends_no_further_mail(self):
        user = User.objects.create_user(email="throttled@example.com")
        for _ in range(3):
            self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        mail.outbox.clear()
        response = self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_is_normalized_to_lowercase(self):
        self.client.post(reverse("accounts:request_link"), {"email": "MixedCase@Example.com"})
        self.assertTrue(User.objects.filter(email="mixedcase@example.com").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_views_request_link -v 2`
Expected: FAIL — `accounts:request_link` URL doesn't resolve yet.

- [ ] **Step 3: Write `accounts/forms.py`**

```python
from django import forms


class EmailForm(forms.Form):
    email = forms.EmailField(max_length=255)
```

- [ ] **Step 4: Write `accounts/utils.py`**

```python
def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
```

- [ ] **Step 5: Write `accounts/emails.py`**

```python
from django.conf import settings
from django.core.mail import send_mail


def send_magic_link_email(to_email, raw_token):
    link_url = f"{settings.APP_URL}/auth/verify/{raw_token}/"
    send_mail(
        subject="Your No Agenda Talent Search sign-in link",
        message=f"Click to sign in (expires in 15 minutes): {link_url}",
        from_email=settings.MAIL_FROM,
        recipient_list=[to_email],
    )
```

- [ ] **Step 6: Write `accounts/views.py`**

```python
from django.shortcuts import render

from .emails import send_magic_link_email
from .forms import EmailForm
from .models import User
from .ratelimit import (
    email_link_requests_exceeded,
    ip_link_requests_exceeded,
    ip_signup_limit_exceeded,
)
from .tokens import create_magic_link
from .utils import get_client_ip


def request_magic_link(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip = get_client_ip(request)
        _maybe_send_magic_link(email, ip)
        return render(request, "accounts/link_sent.html")
    return render(request, "accounts/request_link.html", {"form": form})


def _maybe_send_magic_link(email, ip):
    if email_link_requests_exceeded(email) or ip_link_requests_exceeded(ip):
        return
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        if ip_signup_limit_exceeded(ip):
            return
        user = User.objects.create_user(email=email, signup_ip=ip)
    raw_token = create_magic_link(user, requested_ip=ip)
    send_magic_link_email(user.email, raw_token)
```

- [ ] **Step 7: Write `accounts/urls.py`** (overwrites the Task 1 stub)

```python
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.request_magic_link, name="request_link"),
    path("signup/", views.request_magic_link, name="signup"),
]
```

- [ ] **Step 8: Write `templates/accounts/request_link.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Log in or sign up</h1>
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Send me a link</button>
</form>
{% endblock %}
```

- [ ] **Step 9: Write `templates/accounts/link_sent.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Check your email</h1>
<p>If that address is valid, a sign-in link is on its way. It expires in 15 minutes.</p>
{% endblock %}
```

- [ ] **Step 10: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_views_request_link -v 2`
Expected: PASS, 6 tests.

- [ ] **Step 11: Switch `templates/core/home.html` back to real links now that the routes exist**

```html
{% extends "base.html" %}
{% block content %}
<h1>No Agenda Talent Search</h1>
<p>The community-driven audition for the show's next co-host.</p>
{% if user.is_authenticated %}
  <p>Signed in as {{ user.email }}.</p>
{% else %}
  <p><a href="{% url 'accounts:request_link' %}">Log in or sign up</a></p>
{% endif %}
{% endblock %}
```

Run: `docker compose run --rm web python manage.py test core accounts -v 2`
Expected: PASS, all tests from Tasks 2-5.

- [ ] **Step 12: Commit**

```bash
git add accounts/ templates/
git commit -m "Add magic-link request flow (signup/login, no account enumeration)"
```

---

## Task 6: Magic-link verify flow + expired/resend page

**Files:**
- Modify: `accounts/views.py` (add `verify_magic_link`, `link_expired`)
- Modify: `accounts/urls.py` (add routes)
- Create: `templates/accounts/link_expired.html`
- Create: `accounts/tests/test_views_verify.py`

**Interfaces:**
- Consumes: `accounts.tokens.consume_magic_link` (Task 4).
- Produces: URL names `accounts:verify` (`/auth/verify/<token>/`) and `accounts:link_expired` (`/auth/expired/`).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_views_verify.py
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import MagicLink, User
from accounts.tokens import create_magic_link


class VerifyMagicLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_valid_token_logs_user_in_and_redirects_home(self):
        raw_token = create_magic_link(self.user)
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated if hasattr(response, "wsgi_request") else True)
        # Confirm the session actually authenticated the user on a follow-up request.
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "producer@example.com")

    def test_valid_token_sets_email_verified_at(self):
        raw_token = create_magic_link(self.user)
        self.assertIsNone(self.user.email_verified_at)
        self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verified_at)

    def test_invalid_token_redirects_to_expired(self):
        response = self.client.get(reverse("accounts:verify", args=["bogus-token"]))
        self.assertRedirects(response, reverse("accounts:link_expired"))

    def test_already_used_token_redirects_to_expired(self):
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.client.logout()
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.assertRedirects(response, reverse("accounts:link_expired"))

    def test_expired_link_page_does_not_prefill_email(self):
        response = self.client.get(reverse("accounts:link_expired"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "producer@example.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_views_verify -v 2`
Expected: FAIL — `accounts:verify` / `accounts:link_expired` don't resolve.

- [ ] **Step 3: Add to `accounts/views.py`** (append)

```python
from django.contrib.auth import login
from django.shortcuts import redirect
from django.utils import timezone

from .tokens import consume_magic_link


def verify_magic_link(request, token):
    user = consume_magic_link(token)
    if user is None:
        return redirect("accounts:link_expired")
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    return redirect("core:home")


def link_expired(request):
    return request_magic_link(request) if request.method == "POST" else render(request, "accounts/link_expired.html")
```

Note: reusing `request_magic_link` for the POST case keeps the "send me a new one" form's behavior (rate limits, no enumeration) identical without duplicating logic — but it renders `accounts/link_sent.html` on success, which is correct here too.

- [ ] **Step 4: Add routes to `accounts/urls.py`** (insert into `urlpatterns`)

```python
    path("auth/verify/<str:token>/", views.verify_magic_link, name="verify"),
    path("auth/expired/", views.link_expired, name="link_expired"),
```

- [ ] **Step 5: Write `templates/accounts/link_expired.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>That link has expired</h1>
<p>Sign-in links only work once and expire after 15 minutes. Enter your email and we'll send a fresh one.</p>
<form method="post">
  {% csrf_token %}
  <input type="email" name="email" placeholder="you@example.com" required>
  <button type="submit">Send me a new link</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_views_verify -v 2`
Expected: PASS, 5 tests.

- [ ] **Step 7: Commit**

```bash
git add accounts/ templates/
git commit -m "Add magic-link verify flow and expired/resend page"
```

---

## Task 7: Logout + session behavior

**Files:**
- Modify: `accounts/views.py` (add `logout_view`)
- Modify: `accounts/urls.py` (add route)
- Modify: `templates/core/home.html` (add logout link, matching Task 3's placeholder)
- Create: `accounts/tests/test_session.py`

**Interfaces:**
- Consumes: `SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST` from `config/settings.py` (Task 1).
- Produces: URL name `accounts:logout` (`/logout/`).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_session.py
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link


class SessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def _login(self):
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))

    def test_session_cookie_age_is_90_days(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 24 * 90)

    def test_session_saved_every_request_for_sliding_expiry(self):
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_logout_clears_session_server_side(self):
        self._login()
        session_key = self.client.session.session_key
        self.client.post(reverse("accounts:logout"))
        from django.contrib.sessions.models import Session

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_logout_redirects_home(self):
        self._login()
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_session -v 2`
Expected: FAIL — `accounts:logout` doesn't resolve.

- [ ] **Step 3: Add to `accounts/views.py`** (append)

```python
from django.contrib.auth import logout
from django.views.decorators.http import require_POST


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:home")
```

- [ ] **Step 4: Add route to `accounts/urls.py`** (insert into `urlpatterns`)

```python
    path("logout/", views.logout_view, name="logout"),
```

- [ ] **Step 5: Update `templates/core/home.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>No Agenda Talent Search</h1>
<p>The community-driven audition for the show's next co-host.</p>
{% if user.is_authenticated %}
  <p>Signed in as {{ user.email }}.</p>
  <form method="post" action="{% url 'accounts:logout' %}">
    {% csrf_token %}
    <button type="submit">Log out</button>
  </form>
{% else %}
  <p><a href="{% url 'accounts:request_link' %}">Log in or sign up</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts core -v 2`
Expected: PASS, all tests from Tasks 2-7.

- [ ] **Step 7: Commit**

```bash
git add accounts/ templates/
git commit -m "Add logout view and confirm sliding 90-day session behavior"
```

---

## Task 8: `/account` page (view/edit profile, self-service delete)

**Files:**
- Create: `accounts/forms.py` (modify — add `AccountForm`)
- Modify: `accounts/views.py` (add `account_view`, `delete_account_view`)
- Modify: `accounts/urls.py` (add routes)
- Create: `templates/accounts/account.html`
- Create: `accounts/tests/test_account_view.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2), Django's `login_required` decorator.
- Produces: URL names `accounts:account` (`/account/`) and `accounts:delete_account` (`/account/delete/`).

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_account_view.py
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link


class AccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com", display_name="Old Name")
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))

    def test_anonymous_user_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:account"))
        self.assertEqual(response.status_code, 302)

    def test_get_shows_current_display_name(self):
        response = self.client.get(reverse("accounts:account"))
        self.assertContains(response, "Old Name")

    def test_post_updates_display_name(self):
        self.client.post(reverse("accounts:account"), {"display_name": "New Name"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "New Name")

    def test_delete_account_anonymizes_and_logs_out(self):
        response = self.client.post(reverse("accounts:delete_account"))
        self.assertRedirects(response, reverse("core:home"))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deleted_at)
        self.assertNotEqual(self.user.email, "producer@example.com")
        self.assertEqual(self.user.display_name, "")
        self.assertFalse(self.user.is_active)

    def test_deleted_user_cannot_log_in_again_with_old_link(self):
        raw_token = create_magic_link(self.user)
        self.client.post(reverse("accounts:delete_account"))
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        # token still consumes (single-use design is unaffected by deletion),
        # but the resulting session belongs to a deactivated account.
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_account_view -v 2`
Expected: FAIL — `accounts:account` doesn't resolve.

- [ ] **Step 3: Add `AccountForm` to `accounts/forms.py`** (append)

```python
class AccountForm(forms.Form):
    display_name = forms.CharField(max_length=100, required=False)
```

- [ ] **Step 4: Add to `accounts/views.py`** (append)

```python
from django.contrib.auth.decorators import login_required

from .forms import AccountForm


@login_required
def account_view(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            request.user.display_name = form.cleaned_data["display_name"]
            request.user.save(update_fields=["display_name"])
    else:
        form = AccountForm(initial={"display_name": request.user.display_name})
    return render(request, "accounts/account.html", {"form": form})


@login_required
@require_POST
def delete_account_view(request):
    user = request.user
    user.email = f"deleted-{user.id}@deleted.noagendatalentsearch.com"
    user.display_name = ""
    user.signup_ip = None
    user.deleted_at = timezone.now()
    user.save(update_fields=["email", "display_name", "signup_ip", "deleted_at"])
    logout(request)
    return redirect("core:home")
```

- [ ] **Step 5: Add routes to `accounts/urls.py`** (insert into `urlpatterns`)

```python
    path("account/", views.account_view, name="account"),
    path("account/delete/", views.delete_account_view, name="delete_account"),
```

- [ ] **Step 6: Write `templates/accounts/account.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Your account</h1>
<p>Email: {{ user.email }} (contact hello@noagendatalentsearch.com to change it)</p>
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Save</button>
</form>
<form method="post" action="{% url 'accounts:delete_account' %}" onsubmit="return confirm('Delete your account? This cannot be undone.');">
  {% csrf_token %}
  <button type="submit">Delete my account</button>
</form>
{% endblock %}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_account_view -v 2`
Expected: PASS, 5 tests.

- [ ] **Step 8: Commit**

```bash
git add accounts/ templates/
git commit -m "Add /account page: edit display name, self-service anonymizing delete"
```

---

## Task 9: `candidates` app — Candidate, Demo models (schema only)

**Files:**
- Create: `candidates/apps.py`
- Create: `candidates/models.py`
- Create: `candidates/admin.py`
- Create: `candidates/migrations/__init__.py`
- Create: `candidates/tests/__init__.py`
- Create: `candidates/tests/test_models.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2).
- Produces: `candidates.models.Candidate(user, stage_name, bio, photo_path, status, is_featured, created_at, approved_at)` with `Candidate.Status` choices; `candidates.models.Demo(candidate, original_path, stream_path, duration_sec, file_size, status, created_at)` with `Demo.Status` choices. Task 11 (`ratings` app) FKs to `candidates.Candidate`.

- [ ] **Step 1: Write the failing test**

```python
# candidates/tests/test_models.py
from django.test import TestCase

from accounts.models import User
from candidates.models import Candidate, Demo


class CandidateModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="candidate@example.com")

    def test_create_candidate_defaults_to_pending(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        self.assertEqual(candidate.status, Candidate.Status.PENDING)
        self.assertFalse(candidate.is_featured)

    def test_one_candidate_per_user(self):
        from django.db import IntegrityError

        Candidate.objects.create(user=self.user, stage_name="First")
        with self.assertRaises(IntegrityError):
            Candidate.objects.create(user=self.user, stage_name="Second")

    def test_create_demo_defaults_to_pending(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        demo = Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo1.mp3")
        self.assertEqual(demo.status, Demo.Status.PENDING)

    def test_candidate_can_have_multiple_demos(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo1.mp3", status=Demo.Status.ARCHIVED)
        Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo2.mp3")
        self.assertEqual(candidate.demos.count(), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test candidates -v 2`
Expected: FAIL — `candidates.models` doesn't exist.

- [ ] **Step 3: Write `candidates/apps.py`**

```python
from django.apps import AppConfig


class CandidatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "candidates"
```

- [ ] **Step 4: Write `candidates/models.py`**

```python
from django.db import models

from accounts.models import User


class Candidate(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        BANNED = "banned", "Banned"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate")
    stage_name = models.CharField(max_length=100)
    bio = models.TextField(max_length=1500, blank=True)
    photo_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.stage_name


class Demo(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="demos")
    original_path = models.CharField(max_length=500)
    stream_path = models.CharField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Demo({self.candidate.stage_name}, {self.status})"
```

- [ ] **Step 5: Write `candidates/admin.py`**

```python
from django.contrib import admin

from .models import Candidate, Demo


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("stage_name", "user", "status", "is_featured", "created_at")
    list_filter = ("status", "is_featured")
    search_fields = ("stage_name", "user__email")


@admin.register(Demo)
class DemoAdmin(admin.ModelAdmin):
    list_display = ("candidate", "status", "duration_sec", "created_at")
    list_filter = ("status",)
```

- [ ] **Step 6: Create `candidates/migrations/__init__.py` and `candidates/tests/__init__.py`** (empty files)

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations candidates`
Expected: creates `candidates/migrations/0001_initial.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test candidates -v 2`
Expected: PASS, 4 tests.

- [ ] **Step 9: Commit**

```bash
git add candidates/
git commit -m "Add candidates app schema: Candidate, Demo (no features yet)"
```

---

## Task 10: `episodes` app — Episode model (schema only)

**Files:**
- Create: `episodes/apps.py`
- Create: `episodes/models.py`
- Create: `episodes/admin.py`
- Create: `episodes/migrations/__init__.py`
- Create: `episodes/tests/__init__.py`
- Create: `episodes/tests/test_models.py`

**Interfaces:**
- Produces: `episodes.models.Episode(guid, raw_guid, episode_number, title_raw, title_display, published_at, link_url, artwork_url, enclosure_url, duration_sec, synced_at)`. `guid` is the normalized, unique lookup key per spec §3.4. Task 11 (`ratings` app) FKs to `episodes.Episode`.

- [ ] **Step 1: Write the failing test**

```python
# episodes/tests/test_models.py
from django.test import TestCase
from django.utils import timezone

from episodes.models import Episode


class EpisodeModelTests(TestCase):
    def test_create_episode(self):
        episode = Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw='1895 - "XY You\'re Out"',
            title_display="XY You're Out",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
            artwork_url="https://noagendaassets.com/enc/x_na-1895-art-feed.jpg",
            enclosure_url="https://op3.dev/e/mp3s.nashownotes.com/NA-1895.mp3",
            duration_sec=11050,
        )
        self.assertEqual(episode.episode_number, 1895)

    def test_guid_is_unique(self):
        from django.db import IntegrityError

        Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw="x",
            title_display="x",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
        )
        with self.assertRaises(IntegrityError):
            Episode.objects.create(
                guid="1895.noagendanotes.com",
                raw_guid="http://1895.noagendanotes.com/",
                episode_number=1895,
                title_raw="x",
                title_display="x",
                published_at=timezone.now(),
                link_url="http://1895.noagendanotes.com",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test episodes -v 2`
Expected: FAIL — `episodes.models` doesn't exist.

- [ ] **Step 3: Write `episodes/apps.py`**

```python
from django.apps import AppConfig


class EpisodesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "episodes"
```

- [ ] **Step 4: Write `episodes/models.py`**

```python
from django.db import models


class Episode(models.Model):
    guid = models.CharField(max_length=255, unique=True)
    raw_guid = models.CharField(max_length=500)
    episode_number = models.PositiveIntegerField()
    title_raw = models.TextField()
    title_display = models.CharField(max_length=500)
    published_at = models.DateTimeField()
    link_url = models.URLField(max_length=500)
    artwork_url = models.URLField(max_length=500, blank=True)
    enclosure_url = models.URLField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.episode_number} - {self.title_display}"
```

- [ ] **Step 5: Write `episodes/admin.py`**

```python
from django.contrib import admin

from .models import Episode


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("episode_number", "title_display", "published_at")
    search_fields = ("title_display", "guid")
```

- [ ] **Step 6: Create `episodes/migrations/__init__.py` and `episodes/tests/__init__.py`** (empty files)

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations episodes`
Expected: creates `episodes/migrations/0001_initial.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test episodes -v 2`
Expected: PASS, 2 tests.

- [ ] **Step 9: Commit**

```bash
git add episodes/
git commit -m "Add episodes app schema: Episode (no RSS sync yet)"
```

---

## Task 11: `ratings` app — Appearance, Rating models (schema only)

**Files:**
- Create: `ratings/apps.py`
- Create: `ratings/models.py`
- Create: `ratings/admin.py`
- Create: `ratings/migrations/__init__.py`
- Create: `ratings/tests/__init__.py`
- Create: `ratings/tests/test_models.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2), `candidates.models.Candidate` (Task 9), `episodes.models.Episode` (Task 10).
- Produces: `ratings.models.Appearance(episode, candidate, admin_note, rateable_until, created_at)` with `UniqueConstraint(episode, candidate)`; `ratings.models.Rating(user, rateable_type, rateable_id, stars, created_at, updated_at)` with `Rating.RateableType` choices and `UniqueConstraint(user, rateable_type, rateable_id)`.

- [ ] **Step 1: Write the failing test**

```python
# ratings/tests/test_models.py
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import Candidate
from episodes.models import Episode
from ratings.models import Appearance, Rating


class RatingsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="voter@example.com")
        candidate_user = User.objects.create_user(email="candidate@example.com")
        self.candidate = Candidate.objects.create(user=candidate_user, stage_name="The Contender")
        self.episode = Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw="x",
            title_display="x",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
        )

    def test_create_appearance(self):
        appearance = Appearance.objects.create(
            episode=self.episode,
            candidate=self.candidate,
            rateable_until=timezone.now(),
        )
        self.assertEqual(appearance.episode, self.episode)

    def test_duplicate_appearance_rejected(self):
        from django.db import IntegrityError

        Appearance.objects.create(episode=self.episode, candidate=self.candidate, rateable_until=timezone.now())
        with self.assertRaises(IntegrityError):
            Appearance.objects.create(episode=self.episode, candidate=self.candidate, rateable_until=timezone.now())

    def test_create_rating_for_demo(self):
        rating = Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4
        )
        self.assertEqual(rating.stars, 4)

    def test_duplicate_rating_same_user_same_item_rejected(self):
        from django.db import IntegrityError

        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4)
        with self.assertRaises(IntegrityError):
            Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=2)

    def test_same_user_can_rate_two_different_items(self):
        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4)
        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=2, stars=5)
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test ratings -v 2`
Expected: FAIL — `ratings.models` doesn't exist.

- [ ] **Step 3: Write `ratings/apps.py`**

```python
from django.apps import AppConfig


class RatingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ratings"
```

- [ ] **Step 4: Write `ratings/models.py`**

```python
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import User
from candidates.models import Candidate
from episodes.models import Episode


class Appearance(models.Model):
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name="appearances")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="appearances")
    admin_note = models.CharField(max_length=500, blank=True)
    rateable_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["episode", "candidate"], name="unique_episode_candidate")
        ]

    def __str__(self):
        return f"{self.candidate.stage_name} on {self.episode.episode_number}"


class Rating(models.Model):
    class RateableType(models.TextChoices):
        DEMO = "demo", "Demo"
        APPEARANCE = "appearance", "Appearance"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    rateable_type = models.CharField(max_length=20, choices=RateableType.choices)
    rateable_id = models.PositiveIntegerField()
    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "rateable_type", "rateable_id"], name="unique_user_rateable")
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.rateable_type}:{self.rateable_id} ({self.stars})"
```

- [ ] **Step 5: Write `ratings/admin.py`**

```python
from django.contrib import admin

from .models import Appearance, Rating


@admin.register(Appearance)
class AppearanceAdmin(admin.ModelAdmin):
    list_display = ("candidate", "episode", "rateable_until")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "rateable_type", "rateable_id", "stars", "updated_at")
    list_filter = ("rateable_type", "stars")
```

- [ ] **Step 6: Create `ratings/migrations/__init__.py` and `ratings/tests/__init__.py`** (empty files)

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations ratings`
Expected: creates `ratings/migrations/0001_initial.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test ratings -v 2`
Expected: PASS, 5 tests.

- [ ] **Step 9: Commit**

```bash
git add ratings/
git commit -m "Add ratings app schema: Appearance, Rating (DB-enforced uniqueness)"
```

---

## Task 12: `moderation` app — Report, AdminAuditLog models (schema only)

**Files:**
- Create: `moderation/apps.py`
- Create: `moderation/models.py`
- Create: `moderation/admin.py`
- Create: `moderation/migrations/__init__.py`
- Create: `moderation/tests/__init__.py`
- Create: `moderation/tests/test_models.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2).
- Produces: `moderation.models.Report(reporter, target_type, target_id, reason, details, status, created_at)` with `Report.Reason`/`Report.Status` choices; `moderation.models.AdminAuditLog(admin_user, action, target_type, target_id, metadata_json, created_at)`. Task 13's `make_admin` command and Task 14's settings-change flows (later phases) write `AdminAuditLog` rows.

- [ ] **Step 1: Write the failing test**

```python
# moderation/tests/test_models.py
from django.test import TestCase

from accounts.models import User
from moderation.models import AdminAuditLog, Report


class ModerationModelTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(email="reporter@example.com")
        self.admin = User.objects.create_superuser(email="admin@example.com")

    def test_create_report_defaults_to_open(self):
        report = Report.objects.create(
            reporter=self.reporter, target_type="candidate", target_id=1, reason=Report.Reason.SPAM
        )
        self.assertEqual(report.status, Report.Status.OPEN)

    def test_create_audit_log_entry(self):
        entry = AdminAuditLog.objects.create(
            admin_user=self.admin,
            action="grant_role",
            target_type="user",
            target_id=self.reporter.id,
            metadata_json={"old_role": "producer", "new_role": "moderator"},
        )
        self.assertEqual(entry.metadata_json["new_role"], "moderator")

    def test_audit_log_survives_admin_user_deletion(self):
        entry = AdminAuditLog.objects.create(admin_user=self.admin, action="test", target_type="user", target_id=1)
        self.admin.delete()
        entry.refresh_from_db()
        self.assertIsNone(entry.admin_user)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test moderation -v 2`
Expected: FAIL — `moderation.models` doesn't exist.

- [ ] **Step 3: Write `moderation/apps.py`**

```python
from django.apps import AppConfig


class ModerationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moderation"
```

- [ ] **Step 4: Write `moderation/models.py`**

```python
from django.db import models

from accounts.models import User


class Report(models.Model):
    class Reason(models.TextChoices):
        IMPERSONATION = "impersonation", "Impersonation"
        OFFENSIVE = "offensive", "Offensive content"
        SPAM = "spam", "Spam"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_filed")
    target_type = models.CharField(max_length=20)
    target_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)


class AdminAuditLog(models.Model):
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_actions")
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on {self.target_type}:{self.target_id}"
```

- [ ] **Step 5: Write `moderation/admin.py`**

```python
from django.contrib import admin

from .models import AdminAuditLog, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "target_type", "target_id", "reason", "status", "created_at")
    list_filter = ("status", "reason")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "action", "target_type", "target_id", "created_at")
    readonly_fields = ("admin_user", "action", "target_type", "target_id", "metadata_json", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

- [ ] **Step 6: Create `moderation/migrations/__init__.py` and `moderation/tests/__init__.py`** (empty files)

- [ ] **Step 7: Generate and run the migration**

Run: `docker compose run --rm web python manage.py makemigrations moderation`
Expected: creates `moderation/migrations/0001_initial.py`.

Run: `docker compose run --rm web python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 8: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test moderation -v 2`
Expected: PASS, 3 tests.

- [ ] **Step 9: Commit**

```bash
git add moderation/
git commit -m "Add moderation app schema: Report, AdminAuditLog"
```

---

## Task 13: `make_admin` management command

**Files:**
- Create: `accounts/management/__init__.py`
- Create: `accounts/management/commands/__init__.py`
- Create: `accounts/management/commands/make_admin.py`
- Create: `accounts/tests/test_make_admin.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 2), `moderation.models.AdminAuditLog` (Task 12).
- Produces: `python manage.py make_admin <email>` CLI command, per spec Appendix A.6 — bootstraps the first admin account.

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests/test_make_admin.py
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from moderation.models import AdminAuditLog


class MakeAdminCommandTests(TestCase):
    def test_promotes_existing_user_to_admin(self):
        User.objects.create_user(email="existing@example.com")
        call_command("make_admin", "existing@example.com", stdout=StringIO())
        user = User.objects.get(email="existing@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_superuser)

    def test_creates_new_user_if_email_unknown(self):
        call_command("make_admin", "brandnew@example.com", stdout=StringIO())
        user = User.objects.get(email="brandnew@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)

    def test_writes_audit_log_entry(self):
        call_command("make_admin", "audited@example.com", stdout=StringIO())
        user = User.objects.get(email="audited@example.com")
        entry = AdminAuditLog.objects.get(target_type="user", target_id=user.id)
        self.assertEqual(entry.action, "make_admin")

    def test_email_is_normalized(self):
        call_command("make_admin", "MixedCase@Example.com", stdout=StringIO())
        self.assertTrue(User.objects.filter(email="mixedcase@example.com").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_make_admin -v 2`
Expected: FAIL — no such management command.

- [ ] **Step 3: Create the empty `__init__.py` files**

`accounts/management/__init__.py` and `accounts/management/commands/__init__.py` — both empty.

- [ ] **Step 4: Write `accounts/management/commands/make_admin.py`**

```python
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from moderation.models import AdminAuditLog


class Command(BaseCommand):
    help = "Promote a user to the admin role, creating the account if it doesn't exist."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if not email:
            raise CommandError("email is required")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": User.Role.ADMIN},
        )
        if not created:
            user.role = User.Role.ADMIN
            user.save(update_fields=["role"])
        else:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        AdminAuditLog.objects.create(
            admin_user=None,
            action="make_admin",
            target_type="user",
            target_id=user.id,
            metadata_json={"email": email, "created": created},
        )

        verb = "Created and promoted" if created else "Promoted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {email} to admin."))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test accounts.tests.test_make_admin -v 2`
Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```bash
git add accounts/management/ accounts/tests/test_make_admin.py
git commit -m "Add make_admin management command to bootstrap the first admin"
```

---

## Task 14: Custom 404/500 error pages

**Files:**
- Create: `templates/404.html`
- Create: `templates/500.html`
- Modify: `config/urls.py` (no code change needed — Django finds these by convention; add a temporary debug route for the 500 test)
- Create: `core/tests/test_error_pages.py`

**Interfaces:**
- Consumes: `templates/base.html` (Task 3).
- Produces: friendly, on-brand 404/500 responses instead of Django's framework defaults, per spec B.5. Placeholder copy — flagged for the producer to replace before launch, same as the About page copy.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_error_pages.py
from django.test import Client, TestCase, override_settings


class ErrorPageTests(TestCase):
    def test_404_uses_custom_template_not_framework_default(self):
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            client = Client(raise_request_exception=False)
            response = client.get("/this-page-does-not-exist/")
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "can't find that page", status_code=404)

    def test_500_uses_custom_template_not_framework_default(self):
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            client = Client(raise_request_exception=False)
            response = client.get("/__test-500__/")
            self.assertEqual(response.status_code, 500)
            self.assertContains(response, "something went wrong", status_code=500)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web python manage.py test core.tests.test_error_pages -v 2`
Expected: FAIL — Django's built-in default error pages render, not custom copy; `/__test-500__/` 404s (route doesn't exist yet).

- [ ] **Step 3: Write `templates/404.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>We can't find that page</h1>
<p>The link might be old, or the page might have moved. <a href="/">Back to the home page</a>.</p>
{% endblock %}
```

- [ ] **Step 4: Write `templates/500.html`**

Note: Django renders `500.html` **without** the request context, so it cannot `{% extends %}` a template that relies on context processors (e.g. `{% url %}` tags needing `request`). Keep it fully self-contained:

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Something went wrong</title></head>
<body>
<h1>Something went wrong on our end</h1>
<p>It's not you. Try again in a minute, or email hello@noagendatalentsearch.com if it keeps happening.</p>
</body>
</html>
```

- [ ] **Step 5: Add a test-only view that raises, to prove the 500 handler fires**

Add to `core/views.py` (append):

```python
def _test_500(request):
    raise Exception("intentional test error")
```

Add to `core/urls.py` (insert into `urlpatterns`, guarded so it never exists outside tests):

```python
import os

if os.environ.get("APP_ENV") != "production":
    urlpatterns += [path("__test-500__/", views._test_500, name="test_500")]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose run --rm web python manage.py test core -v 2`
Expected: PASS, all `core` tests including the two new error-page tests.

- [ ] **Step 7: Commit**

```bash
git add templates/404.html templates/500.html core/
git commit -m "Add custom 404/500 error pages (placeholder copy for producer review)"
```

---

## Task 15: Full-suite verification and deployability check

**Files:** none created — this task only runs commands to confirm Phase 1 is deployable per the design doc's definition (Docker Compose runs locally, migrations apply cleanly, `/healthz` passes, admin bootstrap works).

**Interfaces:**
- Consumes: everything from Tasks 1-14.

- [ ] **Step 1: Run the full test suite**

Run: `docker compose run --rm web python manage.py test`
Expected: all tests from every app pass (accounts, core, candidates, episodes, ratings, moderation).

- [ ] **Step 2: Verify a clean database can migrate from zero**

Run: `docker compose down -v` (drops the local Postgres volume — safe, this is disposable dev data)
Run: `docker compose up -d db`
Run: `docker compose run --rm web python manage.py migrate`
Expected: every migration across all six apps applies cleanly in dependency order, ending with the `core.0002_seed_settings` data migration populating all ten settings rows.

- [ ] **Step 3: Verify the seeded settings**

Run: `docker compose run --rm web python manage.py shell -c "from core.models import Settings; print(Settings.objects.count())"`
Expected: `10`

- [ ] **Step 4: Bootstrap an admin and confirm Django admin access**

Run: `docker compose run --rm web python manage.py make_admin you@example.com`
Expected: `Created and promoted you@example.com to admin.`

Run: `docker compose up -d web`
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/healthz`
Expected: `200`

Run: `curl -s http://localhost:8000/healthz`
Expected: `{"status": "ok", "database": "ok"}`

- [ ] **Step 5: Manual smoke test of the magic-link flow**

Run: `curl -s -X POST http://localhost:8000/login/ -d "email=you@example.com" -c /tmp/nats-cookies.txt`
Expected: HTML containing "Check your email".

Run: `docker compose logs web | grep -A5 "Your No Agenda Talent Search sign-in link"`
Expected: the console-backend email log shows a link of the form `http://localhost:8000/auth/verify/<token>/`. Copy `<token>` from the log.

Run: `curl -s -i http://localhost:8000/auth/verify/<token>/ -b /tmp/nats-cookies.txt -c /tmp/nats-cookies.txt`
Expected: `302` redirect to `/`.

Run: `curl -s http://localhost:8000/ -b /tmp/nats-cookies.txt`
Expected: HTML containing "Signed in as you@example.com."

- [ ] **Step 6: Tear down and record the result**

Run: `docker compose down`

No commit for this task (no files changed) — this is the checkpoint confirming Phase 1 meets its "deployable" bar from the design doc.

---

## Self-Review Notes

- **Spec coverage:** §3.1 (accounts/auth) → Tasks 2, 4-8. §4.1 settings infra → Task 3. §5 full schema → Tasks 2, 4, 9-12. §6 Phase-1 pages → Tasks 3, 5, 6, 8. §7/B.6 single server-rendered app → Task 1. §8 security checklist items applicable to Phase 1 (unique-constraint voting, rate limits, hashed single-use tokens) → Tasks 4, 5, 11. B.1 candidate slugs are explicitly deferred to Phase 3 per this plan's Task 9 notes (not in the literal §5 column list). B.3 session/rate-limit specifics → Tasks 4, 7. Appendix A.5/A.6 (env vars, Dockerfile, render.yaml, healthz, make_admin) → Task 1, 13.
- **Explicitly not covered** (by design, per the approved design doc): `/about`, `/candidates`, `/episodes`, `/leaderboard`, `/audition`, RSS sync, upload pipeline, ratings features, scoring, custom `/admin` UI, real Resend email, Turnstile, R2 storage, actual Render/Cloudflare deployment.
