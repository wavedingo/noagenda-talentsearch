# Phase 2 RSS Sync — Implementation Record

**Status:** Complete
**Design:** `docs/superpowers/specs/2026-08-20-phase2-rss-sync-design.md`
**Source spec:** `specs/noagendatalentsearch-spec.md` §3.4, §6, §9 Phase 2, B.5, A.3, A.6

## What was built

| Area | Files |
|---|---|
| Feed parsing (pure, no I/O) | `episodes/feed.py` |
| Fetch + upsert + run recording | `episodes/sync.py` |
| Cron entry point | `episodes/management/commands/rss_sync.py` |
| Schema | `episodes/models.py`, `episodes/migrations/0002_feed_sync.py` |
| Pages | `episodes/views.py`, `episodes/urls.py`, `templates/episodes/{list,detail}.html` |
| Admin (episode manager + manual re-sync) | `episodes/admin.py`, `templates/admin/episodes/episode/change_list.html` |
| Shared chrome | `templates/base.html`, `static/css/site.css`, `templates/core/home.html` |
| Cron declaration | `render.yaml` (`rss-sync`, `*/30 * * * *`) |
| Tests | `episodes/tests/test_{feed_parsing,sync,views}.py`, `episodes/tests/fixtures/feed_sample.xml` |

Schema added this phase: `Episode.feed_guest_hosts` (JSON list) and the `FeedSyncRun` table. Everything else in `episodes` was already created in Phase 1.

## Verified against the live feed (2026-08-20)

```
$ python manage.py rss_sync --dry-run
[dry run] 230 items: 7 created, 0 updated, 223 below floor, 0 unparseable
$ python manage.py rss_sync
230 items: 7 created, 0 updated, 223 below floor, 0 unparseable
$ python manage.py rss_sync            # idempotency
230 items: 0 created, 7 updated, 223 below floor, 0 unparseable
```

Resulting rows: 1890–1896, newest first, 1896 carrying `feed_guest_hosts = ["Rob Dew"]`. Episode 1889 absent, no phantom live-stream episode, no `<description>` text stored on any row, and no `op3.dev` URL rendered on any page.

125 tests pass (73 from Phase 1, 52 added here).

## Notes for whoever picks up Phase 3/4

1. **`Appearance.candidate` should become nullable, with a `guest_name` alongside it** — see decision 3 in the design doc. This is what lets a guest host who never auditioned here be rated, and lets a moderator attach a candidate later without touching a single rating row.
2. **Cache episode artwork into R2** while R2 is being wired for demo audio — the list page currently hotlinks ~400 KB images from the show's asset server.
3. **The local test environment needs Python 3.12**, matching the Dockerfile. Django 5.1 does not run on 3.14 (`Context.__copy__` breaks); the suite errors in a way that looks like application failure but isn't.
4. **`get_setting()`'s 60s locmem cache outlives per-test transaction rollback.** Any test that changes a setting must clear the cache, or it leaks into every test that runs after it in the same process. `episodes/tests/test_sync.py:SyncTestCase` is the pattern.
