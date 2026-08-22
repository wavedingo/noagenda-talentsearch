# Phase 5 — Hardening: Implementation Record

**Design:** `docs/superpowers/specs/2026-08-22-phase5-hardening-design.md`
**Landed:** 2026-08-22
**Tests:** 369 passing

## What shipped

- **Reports** — `/candidates/:slug/report/`, one row per account per candidate, queue at Moderation → Reports. Ten unique open reports set `Candidate.hidden_at`; the public list, detail, home, and leaderboard omit that profile. Resolving/dismissing below 10 unhides. Status stays `live`.
- **Ban / unban / role** — admin-only actions on the user page. Ban sets `banned_at`, flips the candidate to `banned`, recomputes scores. Unban withdraws the profile. Magic-link verify refuses banned and deleted accounts.
- **Account deletion** withdraws any public candidate. Ratings stay attached.
- **Turnstile** — credential-gated on magic-link request and demo upload. Both keys set → verify; either missing → off.
- **30 ratings/min** per account, counted on `Rating.updated_at`.
- **Vote analytics** — Candidates → Vote analytics: 6h / 24h / 7d velocity, spike flag, votes-per-account histogram. Compact vote-delay control on this page and the moderation queue.
- **Blast-radius confirmation** for `vote_eligibility_hours`.
- **Audit log** is admin-only. New actions: `user.ban` / `user.unban` / `user.role_change` / `report.*` / `candidate.auto_hide` / `candidate.unhide`.
- **`send_admin_digest`** and **`backup_database`** management commands, declared in `render.yaml` (`admin-digest` daily 13:00 UTC, `weekly-backup` Sundays 06:00 UTC). Create both in the Render dashboard — the Blueprint is still not live.
- **HSTS** in production. No Django SSL-redirect (Render health checks). Sentry initialises only when `SENTRY_DSN` is set. The image installs **postgresql-client-18** from PGDG (`PG_DUMP_BIN`) because Render Postgres is 18 and Debian's client is 17 — `pg_dump` will not dump a newer server.

## After deploy (producer)

1. Set `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` on the web service (and they already created the widget in A.1). Until both are set, the widgets stay off.
2. Set `ADMIN_NOTIFY_EMAIL` if it should not be `MAIL_FROM`.
3. Create the **admin-digest** and **weekly-backup** crons in the dashboard (same env as the other jobs; backup also needs the five `R2_*` vars so dumps land in `private/backups/`).
4. Optional: `SENTRY_DSN`.
5. Confirm a weekly dump appears in the R2 bucket under `private/backups/`. Test a restore into a scratch database before an on-air announcement (A.8).

## Still producer / ops

UptimeRobot on `/healthz`. Confirm the R2 public domain is read-only. Adopting the Render Blueprint. A restore drill.
