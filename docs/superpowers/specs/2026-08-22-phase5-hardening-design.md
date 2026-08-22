# Phase 5 — Hardening: Design

**Status:** Approved
**Source spec:** `specs/noagendatalentsearch-spec.md` (§3.7, §4, §8, §9 Phase 5, A.7–A.8, B.3)
**Handoff:** `docs/superpowers/plans/2026-08-22-phase4-ratings.md`
**Scope:** Reports, remaining rate limits, Turnstile, vote analytics, ban/user admin, audit-log access, daily digest, backup command, deploy hardening. The site is already live; this phase is the last code before an on-air announcement.

## Decisions

1. **A report targets a candidate, not a demo.** Spec 3.7 puts the button on "candidate profiles/demos." The demo is the thing people listen to, but the abuse (impersonation, offensive photo, spam account) is almost always about the person. One target type (`candidate`) keeps the queue readable and avoids two reports for the same row. Appearances are not separately reportable — they inherit the candidate.

2. **One report per account per candidate.** A second submit updates the open row (reason/details). This is the same shape as ratings: the latest judgement is the one that counts, and a pile-on from one person cannot manufacture a threshold. Unique constraint on `(reporter, target_type, target_id)`.

3. **Auto-hide is a timestamp, not a status flip.** `Candidate.hidden_at` is set when **10 unique open reports** exist. Public list, detail, home, and leaderboard treat a hidden live candidate like a withdrawn one (404 / omitted). Status stays `live` so a moderator resolving the pile can unhide without re-approving the profile. The 10th unique open report is what hides; dropping below 10 unique open reports clears `hidden_at`. Copy never says "hidden because of reports."

4. **Ban is account-level, admin-only.** `ban_user()` sets `User.banned_at`, flips any candidate to `banned`, calls `recompute_scores()`, and writes `user.ban`. `is_active` already fails once `banned_at` is set; magic-link verify refuses to log a banned or deleted account in. Unban clears `banned_at` and sets the candidate to `withdrawn` (they can reopen through the queue — they do not snap back to live). Moderators handle reports; they cannot ban or grant roles.

5. **Deleting an account withdraws the candidate.** Ratings stay attached (spec 3.1). A live profile left behind after self-delete would 404-or-not inconsistently; withdraw is the existing public-off switch.

6. **Turnstile is credential-gated, like Resend and R2.** Both `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` present → widget on magic-link request and demo upload, and the server verifies the token. Either missing → no widget, no check (local/dev, and production until the vars are set on Render). A failed token re-shows the form; it does not change the "link sent" enumeration-safe path, because verification happens *before* `_maybe_send_magic_link`. Their script is the first third-party JavaScript on the site; it is a widget, not an app.

7. **Rating velocity cap is 30 submits per account per minute.** Count `Rating` rows for that user with `updated_at` in the last 60 seconds (a change counts; the point is scripts, not fast raters). Same DB-count style as the existing magic-link limits — no Redis, no new package. Demo upload stays at 5/day (spec 3.2; B.3's "3/day" is the older note and loses).

8. **Vote analytics is a second admin page next to rankings.** Per live candidate: ratings in the last 6 hours / 24 hours / 7 days on their live demo plus appearances, sorted by 24-hour volume. A simple spike flag: 24-hour count ≥ 20 **and** ≥ 3× the 7-day daily average. Site-wide: a votes-per-account histogram (how many accounts have 1 rating, 2, …). No graphs, no extra JS. The compact `vote_eligibility_hours` control lives on this page and on the moderation queue.

9. **Blast-radius confirmation only for `vote_eligibility_hours`.** Changing that key from the settings form or the compact control goes through a confirm step that states: N accounts are currently waiting; this change will immediately make M of them eligible (or re-gate M). Other settings save as they do today. Saving `0` still shows the warning.

10. **Audit log is admin-only.** `AdminAuditLogAdmin` requires `is_superuser`. Moderators keep `ModeratorVisibleAdmin` for candidates, demos, episodes, reports, and settings (operational keys). New writers: `user.ban` / `user.unban` / `user.role_change` / `report.file` / `report.resolve` / `report.dismiss` / `candidate.auto_hide` / `candidate.unhide`.

11. **Daily digest and weekly backup are management commands, not in-request work.** `send_admin_digest` emails `ADMIN_NOTIFY_EMAIL` (or `MAIL_FROM` if unset) with 24-hour signups, pending queue counts, last RSS sync, and spike candidates. `backup_database` writes `pg_dump` (Postgres) or a file copy (SQLite) to `private/backups/` via `default_storage` so it lands in R2 in production. Both are declared in `render.yaml`; the live crons still have to be created in the dashboard. `postgresql-client` is added to the Dockerfile for `pg_dump`.

12. **HSTS yes; Django SSL-redirect no.** Cloudflare already forces HTTPS. `SECURE_SSL_REDIRECT` would 301 Render's internal HTTP health check and take the service down. `SECURE_HSTS_SECONDS = 31536000` in production is safe (only attached to HTTPS responses). Sentry initialises only when `SENTRY_DSN` is set.

## Out of scope

Adopting the Render Blueprint (still a duplicate-service risk). Testing a restore into a scratch database (producer task A.8). UptimeRobot and the Cloudflare "public domain is read-only" confirm (producer tasks). A general Django permission map — local `has_*_permission` overrides stay. Turnstile on every POST (account edit, ratings) — spec names signup and demo upload.
