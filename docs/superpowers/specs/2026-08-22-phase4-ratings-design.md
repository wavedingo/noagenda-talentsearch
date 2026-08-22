# Phase 4 — Ratings: Design

**Status:** Approved
**Source spec:** `specs/noagendatalentsearch-spec.md` (§3.3, §3.5, §3.6, §4, §6, §9 Phase 4, B.5)
**Handoff:** `docs/superpowers/plans/2026-08-20-phase3-auditions.md` (notes for Phase 4)
**Scope:** Demo ratings, appearance tagging, appearance ratings, Bayesian scoring, leaderboard + Rising Demos. No reports, Turnstile, remaining §8 rate limits, or vote-velocity analytics — those are Phase 5.

## Decisions

1. **`Appearance.candidate` is nullable; `guest_name` is always set.** Carried forward from Phase 2 decision 3. A moderator can tag "Rob Dew" from the feed with no candidate row, the audience rates that appearance immediately, and linking a candidate later is an UPDATE on the same row — ratings stay attached because they key on `rateable_id`, not on the candidate. `guest_name` is filled from the feed name or from `candidate.stage_name` at tag time and kept as a snapshot so unlinking (or a later candidate rename) does not blank the appearance. Public copy uses `candidate.stage_name` when linked, `guest_name` otherwise.

2. **Uniqueness is two conditional constraints, not `UNIQUE(episode, candidate)`.** Postgres and SQLite both treat NULLs as distinct in a unique index, so the Phase 1 constraint would allow two unlinked appearances on the same episode. Replace it with: unique `(episode, candidate)` where `candidate` is not null, and unique `(episode, guest_name)` always.

3. **The scoring function is pure; the job writes columns.** Spec §3.6 and §9 name the scoring function as one of the four places a silent bug would hurt most. `ratings/scoring.py` has no ORM: `smooth(R, v, m, C)` and `composite(appearance_score, demo_score, weights)`. `recompute_scores()` is the ORM wrapper: it aggregates countable ratings, writes denormalized columns, and is the only place ranking math meets the database. Page loads never compute scores.

4. **Countable ratings exclude banned accounts, not deleted ones.** Spec 3.1: account deletion anonymizes ratings rather than deleting them, to preserve aggregates. Spec 3.7: a ban soft-deletes the account's ratings from aggregates. Those are different. The scoring query is `Rating.objects.filter(user__banned_at__isnull=True)`. Deleted users (`deleted_at` set, `banned_at` null) still count.

5. **Item averages update on write; the leaderboard uses the job's columns.** A rating `update_or_create` refreshes that item's `rating_avg` / `rating_count` immediately so the 10th vote can cross the display threshold without waiting for the cron. Candidate `demo_score` / `appearance_score` / `composite_score` are written by `recompute_scores()`, which also runs at the end of a successful rating or a tagging change — the dataset is small, and a write-path recompute is not a page-load compute. The hourly cron is the backstop for bans, settings changes, and anything that did not go through those views.

6. **Display threshold and smoothing stay separate.** `min_votes_to_display` (default 10) gates whether a public average is shown. `m=10` (demos) and `m=5` (appearances) are scoring constants, not display rules. Below threshold the copy is "Not enough ratings yet" — never `0.0` or an empty star row (B.5). A closed appearance still shows the final average once past the threshold, with "Ratings for this appearance are closed."

7. **Vote eligibility is computed at request time, not stored.** Spec §4.1: `now >= COALESCE(vote_eligible_override_at, created_at + vote_eligibility_hours)`. A settings change takes effect for everyone currently waiting; existing ratings are never deleted as a side effect. `0` disables the gate. The override is the per-account escape hatch, settable on the user in Django admin.

8. **The rating widget is a POST of five buttons, no JavaScript.** Spec §7 is a server-rendered app. Each star is a submit button; the current rating (if any) is highlighted server-side. Anonymous visitors see "Log in to rate"; ineligible accounts see when they can. Open-redirect protection on `next`.

9. **Only live, playable demos and in-window appearances are rateable.** Pending / archived / rejected demos are not a public signal. Appearances are rateable from the moment they are tagged until `rateable_until`, which is snapshotted at tag time as `episode.published_at + appearance_rating_window_days`. Changing the setting does not rewrite existing windows (a moderator can edit `rateable_until` on the row). Tagging after the window has closed creates a closed appearance — useful for history, not for brigading.

10. **Episode-list badges mean tagged appearances, not feed names.** Phase 2 design decision 2, delayed until this phase because there were no appearances yet. B.5: badge episodes that have tagged guest-host appearances. Feed-declared names remain visible on the episode page as sourced feed fact, and as one-click suggestions on the tagging screen. They do not, by themselves, make an episode rateable or badged.

11. **The public leaderboard never numbers the bottom, and does not use ordinals on the top either.** Top N by `composite_score` among live candidates who have at least one appearance; Rising Demos is live candidates with zero appearances, top N by smoothed demo score. No `#1` / `#2` — the list is the celebration; ordinals invite a race the copy says this is not. Full rankings with raw vs. smoothed scores live in Django admin. Withdrawn / rejected / banned candidates are skipped by the job (their item-level history stays).

12. **Unlinked appearances are rateable but do not enter the leaderboard** until a candidate is linked. Their ratings still move `C_appearances` (the site-wide prior). A guest host who never auditioned here can be rated the night they appear; claiming a profile later carries those ratings onto that candidate's appearance score automatically.

13. **Settings are editable in Django admin; blast-radius confirmation stays in Phase 5.** Weights, windows, and eligibility live in `core.Settings` and are read via `get_setting()`. Moderators can change operational keys (including `vote_eligibility_hours` and `appearance_rating_window_days`) at `/django-admin/` → Core → Runtime settings; score weights and `min_episode_number` stay admin-only. The blast-radius confirmation for `vote_eligibility_hours`, compact controls on the queue, and brigading graphs belong with the rest of the admin panel work.

## Scoring (exact)

```
smooth(R, v, m, C) = (v/(v+m))·R + (m/(v+m))·C
```

- **Demo score** (candidate): `smooth` of the current **live** demo's mean and vote count, `m=10`, `C=C_demos`. Archived-demo ratings never feed the composite. No live demo → `v=0` → the prior `C_demos`.
- **Appearance score** (candidate): each of the candidate's appearances is smoothed with `m=5`, `C=C_appearances`, then averaged unweighted. Zero appearances → the candidate is not on the main board.
- **Composite:** `score_weight_appearance · appearance_score + score_weight_demo · demo_score` (defaults 0.7 / 0.3).
- **Priors `C_demos` / `C_appearances`:** mean of countable stars across all live demos and all appearances respectively, in the same job. No ratings yet → **3.5**.

## Schema added this phase

On `Appearance`: `guest_name`; `candidate` nullable / `SET_NULL`; the two conditional unique constraints; `rating_avg`, `rating_count`, `smoothed_score`.

On `Demo`: `rating_avg`, `rating_count`, `smoothed_score`.

On `Candidate`: `demo_score`, `appearance_score`, `composite_score`.

On `Rating`: index `(rateable_type, rateable_id)` for the aggregate queries.

## Pages

- **`/candidates/:slug`** — star widget on the live demo; appearance history with per-appearance widgets and links to the episode.
- **`/episodes/:number`** — one widget per tagged appearance; feed names still listed as feed fact; closed-window copy per B.5.
- **`/leaderboard`** — Community favorites + Rising Demos, advisory copy, empty state that does not look broken when nobody has been on the show yet.
- **`/candidates?sort=top`** — live candidates by `demo_score` (the "top demos" sort §6 deferred from Phase 3).
- **`/`** — community favorites (or Rising Demos if the main board is empty) above latest episodes.
- **Nav** — Favorites → `/leaderboard`.

Admin, still inside Django admin:

- **Episodes → Appearances** on an episode: tag from a live candidate or a guest name, one-click the feed-declared names, link a candidate onto an unlinked row, remove an appearance (and its ratings — a deliberate untag, audited).
- **Candidates → Full rankings** — every live candidate, raw averages, vote counts, smoothed demo / appearance / composite. Not public.

## Out of scope

Reports and auto-hide thresholds; Turnstile; the rest of §8's rate limits (30 ratings/min included); vote-velocity / votes-per-account graphs; the `vote_eligibility_hours` blast-radius confirmation UI; a dedicated `/appearances/:id` URL (episode detail plus candidate history cover spec 3.5's "appearance pages"); episode-artwork R2 caching (still a follow-up from Phase 2).
