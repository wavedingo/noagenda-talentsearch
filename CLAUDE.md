# noagendatalentsearch.com

A community-driven audition platform to help the No Agenda audience find a permanent
co-host, built after the death of co-host John C Dvorak. Producers submit demo tapes,
the audience rates them and rates guest-host appearances, and the production team uses
that signal. **Ratings inform the show's decision; they don't decide it.**

The people using this are grieving and putting themselves forward in public. Copy and
design choices should reflect that — celebrate the top, never publicly rank the bottom,
and write moderation notices like a person wrote them.

## Where things are

- **`specs/noagendatalentsearch-spec.md`** — the master spec. Read the relevant section
  before changing behaviour; it is kept current, including a deployment checklist
  (Appendix A) with live tick state.
- **`docs/superpowers/specs/`** — per-phase design docs (decisions and why).
- **`docs/superpowers/plans/`** — per-phase implementation records and handoff notes.

## Build phases (spec §9)

| Phase | Scope | Status |
|---|---|---|
| 1 | Scaffold, schema, magic-link auth, admin role | Done |
| 2 | RSS sync, episode pages | Done |
| 3 | Auditions: profile CRUD, mp3 pipeline, moderation queue, candidate pages | Done |
| 4 | Ratings, appearance tagging, Bayesian scoring, leaderboard | Done |
| 5 | Reports, rate limits, Turnstile, analytics, audit log, backups, deploy | |

Each phase ends deployable. Read the previous phase's plan doc for its handoff notes
before starting the next one.

## Stack and conventions

- **Django 5.1, server-rendered.** No SPA, no REST API, no frontend framework. Postgres
  in production (Render), SQLite locally.
- Apps: `accounts`, `core`, `candidates`, `episodes`, `ratings`, `moderation`.
- **Admin is at `/django-admin/`**, not `/admin/`.
- **Runtime settings live in the `core.Settings` table**, read via `get_setting(key)`.
  Environment variables seed them on first boot only — never read config from the
  environment at request time (spec §4.1).
- Dependencies are added sparingly and pinned to a minor series in `requirements.txt`.
- One small hand-written stylesheet (`static/css/site.css`), mobile-first. Most of this
  audience is on a phone.

## Local development

```bash
uv venv --python 3.12 .venv          # Django 5.1 does NOT run on Python 3.14
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
brew install ffmpeg                  # ffprobe validation + transcoding

export SECRET_KEY=dev-secret APP_ENV=development
export DATABASE_URL="sqlite:///$PWD/dev.sqlite3"
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test      # 323 tests
.venv/bin/python manage.py runserver
```

Auth is magic-link only, so there is no password to log in with locally. Mint a link:

```python
from accounts.models import User
from accounts.tokens import create_magic_link
print(create_magic_link(User.objects.get(email="...")))   # visit /auth/verify/<token>/
```

`manage.py make_admin <email>` promotes an account. Magic links are single-use — reusing
one silently lands you on the login page, which is easy to mistake for a broken view.

## Things that will bite you

**Never render `Episode.enclosure_url`.** It carries an OP3 analytics prefix, and every
request through it registers as a download in the show's own statistics. Link to
`link_url` (the show-notes page) instead. The column exists for provenance only.

**Never render the feed's `role="host"` people.** The feed lists John C Dvorak as host on
229 of 230 items — including the tribute episode and everything published since. Only
`role="guest host"` is curated and real. Displaying feed host data would print his name
as host of episodes he was not on, on the one site built around that absence.

**Pre-moderation is a column split, not a status flip.** On `Candidate`, `stage_name` /
`bio` / `photo_path` are the *approved* copy and the only fields a public template may
read. A live candidate's edits go to `pending_*` until a moderator promotes them. Don't
"simplify" this into setting `status = pending` on edit.

**Demo originals are never served.** Only the transcoded stream copy has had its ID3 tags
stripped; the original still carries whatever the uploader's machine wrote, often a real
name. Originals live under the `private/` storage prefix, stream copies under `public/`.

**Storage and email switch on credentials.** Five `R2_*` variables present → Cloudflare
R2; any missing → local disk (which on Render means uploads vanish at the next deploy).
`RESEND_API_KEY` present → real email; absent → console backend.

**Tests that change a runtime setting must clear the cache.** `get_setting()` caches for
60s in a process-wide locmem cache that outlives a test's transaction rollback. See
`candidates/tests/helpers.MediaTestCase` and `episodes/tests/test_sync.SyncTestCase`.

**Background transcoding is off under `manage.py test`** (`DEMO_PROCESS_IN_BACKGROUND`),
so a worker thread never races a test's own rollback. The one test that genuinely crosses
a thread boundary is a `TransactionTestCase`.

**Django's `{# #}` is single-line only.** A multi-line one renders as visible body text.
Use `{% comment %}`. There are regression tests asserting no template syntax reaches a
rendered page.

## Testing

Spec §9 names four places where a silent bug would hurt most, and all four have tests:
the scoring function (Phase 4), vote uniqueness (Phase 4), **upload validation**, and
**RSS idempotency**. Upload validation is tested against files ffmpeg actually produced —
a mocked probe would happily agree that a `.wav` renamed to `.mp3` is an MP3.

## Landing work

Design doc first, then implement, then scoped commits on a branch, then fast-forward
`main` so history stays linear. Commit messages explain *why*, not what. Don't push
without being asked.
