# Phase 1 — Foundation: Design

**Status:** Approved
**Source spec:** `specs/noagendatalentsearch-spec.md` (§9 Phase 1), `specs/about-page-and-house-rules.md`
**Scope:** Project scaffold, DB schema + migrations, magic-link auth, account pages, admin role — per §9 Phase 1. Nothing from Phases 2–5 (RSS sync, auditions, ratings, hardening) gets features or UI in this pass, even though its tables are created now.

## Decisions made in brainstorming

1. **Full §5 schema now.** All tables (users, candidates, demos, episodes, appearances, ratings, reports, magic_links, admin_audit_log, settings) get Django models + migrations in Phase 1, even though only auth-related tables have working features. Rationale: avoids risky schema-adding migrations threaded through later phases; later phases focus purely on behavior.
2. **"Deployable" = Docker Compose runs locally.** Dockerfile + docker-compose.yml (app + Postgres), migrations apply cleanly, `/healthz` passes, admin bootstrap CLI works. `render.yaml` is written and correct but not pushed to an actual Render account — the producer hasn't done Appendix A.1–A.4 (Cloudflare/Resend/Render/R2 signups) yet, so there's nothing live to deploy to.
3. **Admin = Django's built-in admin for now.** No hand-built `/admin` UI in Phase 1. `django.contrib.admin` is wired up (role → `is_staff`/`is_superuser`) for inspecting data. The custom `/admin` from spec §4 gets built incrementally, alongside each feature it manages, in Phases 2–5.
4. **Console email backend.** No real Resend integration this pass — no API key exists yet (that's producer task A.2). Magic links print to server logs. Flagged as a pre-launch follow-up, not a Phase 1 gap.

## Architecture

Single Django project, server-rendered templates only — no separate SPA/API layer (spec §7, B.6).

Apps:
- **`accounts`** — custom `User` model, magic-link auth, sessions, rate limiting, `/account` page
- **`candidates`**, **`episodes`**, **`ratings`**, **`moderation`** — models + migrations only in Phase 1; no views, no features
- **`core`** — `Settings` model, `get_setting()` helper, `/healthz`, base templates, minimal home page stub

Postgres via Docker Compose (`web` + `db`). Dockerfile installs `ffmpeg` now (unused until Phase 3) so the image doesn't need rework later.

## Data model

Implements spec §5 in full. Two additions beyond the spec's literal column list, both needed to implement the B.3 rate limits without introducing Redis:
- `User.signup_ip` — supports "5 signups per IP per day"
- `MagicLink.requested_ip` — supports "10 link requests per IP per hour"

`User` is a custom model (`AbstractBaseUser`), `email` as `USERNAME_FIELD`, no usable password ever set (`set_unusable_password()`). `role` (`producer|moderator|admin`) maps onto Django's staff/superuser flags so `django.contrib.admin` works without extra plumbing:
- `is_staff = role in {moderator, admin}`
- `is_superuser = role == admin`

A "candidate" remains just a producer with a `Candidate` row attached (§5) — no separate role.

## Auth flow

`/login` and `/signup` are the same view/template (email address only) — the spec requires identical responses whether or not the account exists, so there's no reason to fork the code path.

1. Submit email → rate-limit checks (3 link requests/email/hr, 10/IP/hr) → create `User` if new (`signup_ip` recorded, checked against 5/IP/day) → issue `MagicLink` (random token; only its sha256 hash is stored; 15-min expiry; `requested_ip` recorded) → send via console backend.
2. `/auth/verify/<token>/` — hash lookup. Invalid, expired, or already-used → `/auth/expired` (friendly copy + a resend form that does **not** prefill the email address), never a raw 403/404. Valid → mark `used_at`, set `email_verified_at` if unset, log in.
3. Session: 90-day sliding window (`SESSION_SAVE_EVERY_REQUEST=True`), cookie is HttpOnly + Secure + SameSite=Lax.
4. Logout clears the session server-side (Django's `logout()`), not just the cookie.

## Settings infrastructure (§4.1)

`Settings(key, value_json)`. Seeded once via a data migration reading env vars, using `get_or_create` per key — safe to re-run, never overwrites a value an admin has since changed. All ten §4.1 settings are seeded now even though Phase 1 only has a consumer for `vote_eligibility_hours` (and doesn't yet call it from anywhere, since voting doesn't exist until Phase 4 — the row exists so later phases have nothing to migrate).

`get_setting(key)` lives in `core`, backed by Django's locmem cache with a 60s TTL — matches the spec's literal "short in-process cache" wording. No setting is ever read directly from `os.environ` at request time past first boot.

## Pages (Phase 1 subset of §6)

`/`, `/login`, `/signup`, `/auth/verify/<token>/`, `/auth/expired`, `/account` (email, display name, self-service delete — anonymizes the row rather than hard-deleting, consistent with the spec's later ratings-preservation requirement even though no ratings exist yet), `/healthz`, and Django's built-in `/django-admin/`.

Explicitly **not** built this phase: `/about`, `/candidates`, `/episodes`, `/leaderboard`, `/audition` — no content or data to back any of them yet.

## Error handling

Custom 404/500 templates (not framework defaults, per B.5) with minimal placeholder copy — flagged for the producer to review/replace before launch, same as the About page copy.

## Testing

Django's built-in `TestCase` — no new test-runner dependency. Covers:
- Magic link: single-use, 15-min expiry, hash-not-plaintext storage
- No account-enumeration (identical response for existing vs. new email)
- Rate limits (email/hr, IP/hr, signup/IP/day)
- Role → `is_staff`/`is_superuser` mapping
- Settings seed migration idempotency (`get_or_create` behavior)
- `get_setting()` cache TTL behavior
- Session sliding-expiration behavior

## Explicitly out of scope for Phase 1

RSS sync, candidate/demo CRUD and upload pipeline, ratings, scoring, leaderboard, reports, custom `/admin` UI, real email delivery, Turnstile, R2 storage, any actual push to Render/Cloudflare. All per spec §9 Phases 2–5.
