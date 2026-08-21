# Phase 2 — RSS Sync: Design

**Status:** Approved
**Source spec:** `specs/noagendatalentsearch-spec.md` (§3.4, §6, §9 Phase 2, B.5, A.3, A.6)
**Scope:** Feed fetcher + cron, episode list and detail pages. No ratings, no appearance tagging, no candidate data — those are Phases 3–4.

## Feed reconnaissance (2026-08-20)

The spec's §3.4 field mappings were verified against a live fetch of `https://feeds.noagendaassets.com/noagenda.xml`. All confirmed. Four findings beyond what §3.4 records:

1. **The feed is a rolling window, not a full archive.** 230 `<item>` elements, episodes 1667–1896. Spec §3.4 asked for this to be verified before promising an archive — it is now answered: the feed is a window, so `/episodes` must be labelled as covering the show's current era rather than presenting as a complete archive. With the floor at 1890 this is currently moot (7 episodes are eligible), but the sync must never treat "episode fell out of the window" as "episode deleted."

2. **The `podcast:` namespace URI in this feed is not the canonical one.** It resolves to `https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md`, not `https://podcastindex.org/namespace/1.0`. Any parser that hardcodes a namespace URI would silently find nothing. The parser matches elements by **local name**, ignoring the namespace URI entirely.

3. **`podcast:liveItem` is a child of `<channel>`, not an `<item>`.** The spec's warning about a phantom "Episode 1895 - Live" holds, but the mechanism is milder than feared: iterating `channel.findall('item')` skips it structurally. A test asserts this rather than trusting it.

4. **The feed declares guest hosts — and its `host` role is dangerously stale.** Items carry `<podcast:person>` elements. Across all 230 items:
   - `role="host"` appears 459 times: Adam Curry (230) and **John C Dvorak (229)** — including episode 1889, the producer tribute to him, and episodes 1890–1896 published after his death. This role is a boilerplate template value, not curated data.
   - `role="guest host"` appears **once**: Rob Dew on episode 1896. This one is hand-maintained and real.

   **Consequence: this site ingests `role="guest host"` only, and never renders anything from `role="host"`.** Displaying the feed's host data would print John's name as host of episodes he was not on, on the one site built around that absence. The `host` role is not stored, not displayed, not used.

## Decisions

1. **Capture and display feed-declared guest hosts.** Not in the spec's §3.4 field list, added deliberately. Rationale: guest hosts reach the show through the production team, not through this site — Rob Dew already has — and the audience should be able to rate an appearance regardless of whether that person ever auditioned here. The feed is the only record of who hosted, it is a rolling window, and names not captured now age out permanently. Stored on the episode as an ordered list of names; displayed as sourced feed fact ("as listed in the show's feed"), with no rating control and no candidate link in this phase.

2. **Feed guest hosts and admin-curated appearances stay separate concepts.** An `Appearance` (§3.5) is an admin's deliberate act with a rating window attached; a feed guest-host name is just what the XML said. The episode list badges on *appearances*, per B.5, not on feed names — so the badge continues to mean what the spec says it means once Phase 4 lands.

3. **Phase 4 note — "claim a profile."** When appearance tagging is built, `Appearance.candidate` should become nullable with a `guest_name` field alongside it. A moderator can then create an appearance from a feed-declared name with no candidate attached, the audience rates it immediately, and when identity is later verified the moderator links a candidate — every existing rating carries over untouched, because `Rating` is keyed on `rateable_id` (the appearance), not on the candidate. This avoids stub candidate rows, avoids reserving a slug for someone who never signed up, and avoids a rating migration. Recorded here so Phase 2's capture step has a destination; the schema change belongs to Phase 4.

4. **Sync health is a table, not a settings row.** `FeedSyncRun` records every attempt (status, counts, error, duration). The spec needs consecutive-failure alerting after 3 (§3.4) and RSS sync status in the daily admin digest (§A.8, Phase 5); both read from this table. Keeping runtime state out of `settings` preserves that table's meaning as admin-editable configuration.

5. **Episode detail page ships this phase, without rating widgets.** §6 lists `/episodes/:number` as "episode detail + appearance rating widgets"; the widgets are Phase 4. The page ships now as a shell so the list is clickable and the URL exists before anything links to it.

6. **Minimal shared stylesheet.** Phase 2 is the first real data on screen. One small mobile-first CSS file plus a nav in `base.html` — no framework. B.5's mobile-first requirement starts being met here rather than being deferred to a big design pass.

## Sync command

`python manage.py rss_sync [--dry-run]`, run by cron every 30 minutes (`*/30 * * * *`) and triggerable from Django admin.

**Fetch.** `requests.get` with a 30s timeout and a descriptive User-Agent. Non-200, timeout, connection error, unparseable XML, or **a parse yielding zero items** all count as a failed run — the spec is explicit that an empty feed is a failure, not a deletion event. Nothing is written on a failed run. After 3 consecutive failures the command logs at `ERROR` (the alert channel itself is Phase 5's digest email); below that, `WARNING`.

**Parse, per `<item>` child of `<channel>`:**

| Field | Source | Rule |
|---|---|---|
| `raw_guid` | `<guid>` | stored verbatim |
| `guid` | `<guid>` | normalized: lowercase, strip scheme, strip trailing slash — the unique key |
| `episode_number` | `<title>` | `^\s*(\d+)`; unparseable → skip item as a parse failure (logged), *not* as below-floor |
| `title_raw` | `<title>` | verbatim, unmodified |
| `title_display` | `<title>` | strip `NNNN - ` prefix, strip wrapping straight/curly quotes, `.strip()` |
| `published_at` | `<pubDate>` | RFC 822 → aware datetime |
| `link_url` | `<link>` | show-notes page — the only link the site ever renders |
| `artwork_url` | `<itunes:image href>` | by local name |
| `enclosure_url` | `<enclosure url>` | stored for provenance, **never rendered or fetched** (OP3 analytics prefix — see below) |
| `duration_sec` | `<itunes:duration>` | integer seconds |
| `feed_guest_hosts` | `<podcast:person role="guest host">` | ordered list of names; `role="host"` ignored entirely |
| — | `<description>` | **not imported** (§3.4) |

**Floor.** Items numbering below `min_episode_number` (runtime setting, §4.1, default 1890) are skipped silently after the number is parsed. Lowering the setting backfills on the next sync, to the depth the window still carries.

**Upsert.** `update_or_create` on normalized `guid`. Idempotent by construction: a second identical run writes no new rows. Episodes already stored are never deleted for being absent from the feed — the window scrolls, the site's record does not.

**Item-level failure isolation.** Each item is parsed inside its own `try`; a failure logs the item and continues. One malformed item never aborts a sync or affects the other 229.

## Pages

- **`/episodes`** — newest first, 20 per page (B.5), artwork, cleaned title, number, date, duration. Episodes with tagged appearances get a badge (no appearances exist until Phase 4; the code path ships now). Header copy states the list covers the show's current era and starts at the floor, so it doesn't read as a broken archive. Empty state: "No episodes synced yet."
- **`/episodes/<number>`** — artwork, title, number, publish date, duration, feed-declared guest hosts, and a link out to the show-notes page. `<number>` is the display-only episode number, not the key; a number matching no episode 404s. Placeholder for the Phase 4 rating widget where the appearance section will go.

**Artwork is hotlinked, for now.** `artwork_url` points at `noagendaassets.com`, and the feed art is full-size — roughly 400 KB per episode. Rendered at 72 px in the list with `loading="lazy"`, so a phone fetches only what scrolls into view, but a full page of 20 is still several megabytes off the show's own asset server. **Follow-up for Phase 3**, when R2 is being wired for demo audio anyway: cache episode artwork into R2 at sync time and serve a resized copy from the site's own CDN domain. Not worth adding an R2 dependency in this phase for it.

**The enclosure URL is never rendered.** Per §3.4, every request through the OP3 prefix registers as a download in the show's own statistics. Episode pages link to `link_url` only. The column is stored for provenance and is not referenced in any template.

## Testing

Django `TestCase`, plus a trimmed real-feed fixture (`episodes/tests/fixtures/feed_sample.xml`) built from the 2026-08-20 fetch so the parser is tested against the feed's actual quirks, not an idealized one.

- **Idempotency** (called out in §9): sync twice → identical row count, no duplicates
- GUID normalization: `http://`/`https://`, trailing slash, and case variants all resolve to the same row rather than duplicating the catalogue
- Episode floor: 1889 absent, 1890 present; lowering the setting backfills; raising it doesn't error or delete
- `podcast:liveItem` creates no episode
- No `<description>` text is stored on any row
- Unparseable item is skipped and logged; the rest of the feed still syncs
- Fetch failure, HTTP error, and zero-item parse each leave existing rows untouched and record a failed run
- Consecutive-failure counting reaches the alert threshold at 3
- Title cleaning against real feed titles, including the trailing-whitespace case
- `role="host"` names are never stored (regression guard on the John C Dvorak finding); `role="guest host"` names are
- Views: pagination, ordering, empty state, 404 on unknown number, and that no template renders an `op3.dev` URL

## Out of scope for Phase 2

Appearance tagging and rating widgets, candidate data, leaderboard, custom `/admin` UI beyond a re-sync action in Django admin, Sentry alerting on sync failure (Phase 5's digest), and the "claim a profile" flow described in decision 3.
