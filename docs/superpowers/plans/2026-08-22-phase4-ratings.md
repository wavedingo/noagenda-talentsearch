# Phase 4 — Ratings: Implementation Record

**Design:** `docs/superpowers/specs/2026-08-22-phase4-ratings-design.md`
**Landed:** 2026-08-22
**Tests:** 323 passing

## What shipped

- **`ratings/scoring.py`** — pure `smooth` / `appearance_score` / `composite`. No ORM.
- **`ratings/eligibility.py`** — request-time vote gate from `vote_eligibility_hours` and `vote_eligible_override_at`.
- **`ratings/services.py`** — `submit_rating` (`update_or_create`), appearance tag/link/untag, item averages, `recompute_scores`.
- **Public pages** — star widgets on candidate and episode pages, `/leaderboard`, `/candidates?sort=top`, home favorites, appearance history.
- **Admin** — episode appearance tagging (feed-name suggestions, link a candidate, untag), Candidates → Full rankings.
- **`manage.py recompute_scores`** and a `recompute-scores` Render cron declaration (`0 * * * *`). Create the dashboard cron when this lands — `render.yaml` is still not the live source of truth.

## Schema

`Appearance.candidate` is nullable with `guest_name` always stored. Unique `(episode, candidate)` where linked, unique `(episode, guest_name)` always. Denormalized `rating_avg` / `rating_count` / `smoothed_score` on demos and appearances; `demo_score` / `appearance_score` / `composite_score` on candidates.

## Notes for Phase 5

1. Create the **`recompute-scores` cron in the Render dashboard** (hourly, same env as the web service: `DATABASE_URL`, `SECRET_KEY`, `APP_ENV=production`).
2. **Settings UI** with the `vote_eligibility_hours` blast-radius confirmation still is not built — change settings via the `core.Settings` table / shell.
3. Reports, Turnstile, the rest of §8's rate limits (including 30 ratings/min), and vote-velocity analytics are still outstanding.
4. Moderator permissions are still the local `ModeratorVisibleAdmin` / `has_view_permission` overrides, not a general role map.

## Local development

Same as Phase 3. After migrate:

```
python manage.py recompute_scores
```

Vote eligibility defaults to 48 hours. For local rating tests, either wait, set `vote_eligible_override_at` on the user, or `Settings.objects.filter(key="vote_eligibility_hours").update(value_json=0)` and restart / wait 60s for the cache (or `cache.clear()`).
