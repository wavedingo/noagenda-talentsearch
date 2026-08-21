# Phase 3 — Auditions: Implementation Record

**Design:** `docs/superpowers/specs/2026-08-20-phase3-auditions-design.md`
**Landed:** 2026-08-20
**Tests:** 250 passing (134 before this phase)

## What shipped

- **`candidates/audio.py`** — ffprobe-based container and codec inspection, duration limits, and the 128 kbps transcode with `-map_metadata -1` and `-vn`. No DB, no storage, no network.
- **`candidates/images.py`** — Pillow photo pipeline: format allow-list, decompression-bomb guard, orientation applied then EXIF discarded by re-encoding to JPEG inside 600×600.
- **`candidates/storage.py`** — the `private/` (originals) and `public/` (stream copies, photos) key layout, UUID path components, and the local-copy helpers ffmpeg needs. Everything goes through `default_storage`.
- **`candidates/tasks.py`** — the transcode queue: atomic claim, background thread behind a one-slot semaphore, stale reclaim, `drain_queue`.
- **`candidates/services.py`** — profile save with the draft/approved split, demo submission with archival of the previous demo, withdraw/reopen, and the six moderation outcomes. Both the public views and the admin queue call these, so approval means one thing.
- **`candidates/views.py` + templates** — `/candidates`, `/candidates/:slug`, `/audition` and its POST endpoints.
- **Moderation queue** in Django admin, with an inline player, a side-by-side diff for profile edits, canned rejection reasons, and a manual "process queued demos" button.
- **`manage.py process_demos`** and a `process-demos` Render cron every 15 minutes.
- **R2 storage switch** in `config/settings.py`, active as soon as the five `R2_*` variables are set.

## Verified by hand, not just by tests

A real 2.8 MB / 256 kbps / 90-second MP3 was uploaded through a browser against the dev server. It was accepted, stored under `private/`, transcoded by the background thread with no command run by hand, and the page showed "ready" on reload. The stored original still carried `artist: Should Be Stripped`; the served stream copy was 128 kbps with the tag gone. The previous demo was archived automatically.

## Notes for Phase 4

1. **`Appearance.candidate` should become nullable with a `guest_name` alongside it** — carried forward from the Phase 2 design, still the right shape for the "claim a profile" flow. Nothing in Phase 3 blocks it.
2. **"Top demos" sort on `/candidates`** is deliberately absent. §6 lists it, but it needs the scoring columns to mean anything; add it with the scoring job rather than shipping a sort that orders by nothing.
3. **Appearance history** on the candidate detail page is a labelled placeholder. The heading and empty state are already there.
4. **Demo ratings key on the demo row, not the candidate.** Uploading a replacement archives the old demo and its ratings stay attached to it, which is what "new demo = new rating slate" means in §3.2 — no rating migration needed when a candidate re-uploads.

## Notes for Phase 5

1. **Moderator permissions are a local fix, not a general one.** `User.has_perm` still grants only admins; `ModeratorVisibleAdmin` in `candidates/admin.py` opens up just the two models moderators need. A proper role→permission mapping belongs with the audit-log and user-management work.
2. **Upload rate limiting was pulled forward** (5 demos per account per day). The rest of §8's limits — per-IP, ratings, Turnstile on upload — are still outstanding.
3. **`/private/*` must be blocked at Cloudflare** once R2 is live. Added to the A.4 checklist. The app never links to originals and the keys are UUIDs, but the public custom domain serves the whole bucket.
4. `manage.py check --deploy` still reports HSTS, SSL-redirect, and SECRET_KEY warnings — unchanged from Phase 1, still Phase 5's job.

## Local development

- **Python 3.12** (`uv venv --python 3.12 .venv`). Django 5.1 does not work on 3.14.
- **ffmpeg and ffprobe** must be on `PATH` (`brew install ffmpeg`), or set `FFMPEG_BIN`/`FFPROBE_BIN`. The Dockerfile already installs them.
- Tests that change a runtime setting must clear the cache — `MediaTestCase` in `candidates/tests/helpers.py` does it for this app.
- `DEMO_PROCESS_IN_BACKGROUND` is off under `manage.py test`, so a worker thread never races a test's own transaction rollback. The one test that does cross a thread boundary is a `TransactionTestCase`.
