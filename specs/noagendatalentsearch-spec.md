# noagendatalentsearch.com — Product & Technical Specification

**Version:** 1.0 (draft for implementation)
**Owner:** Show producer
**Purpose:** A community-driven audition platform to help identify a permanent co-host for the show, modeled on the "revolving guest host" approach (Live with Regis-style) and on the simplicity of noagendaartgenerator.com.

---

## 1. Overview & Philosophy

The show's audience ("producers") has always contributed directly to the show — clips, artwork, tips. This site extends that tradition to the search for a new co-host. Community members audition by submitting a demo tape; the audience rates demos and rates guest-host performances on actual episodes; the production team uses that signal to decide who to invite back and, eventually, who becomes permanent.

**Guiding principles:**

1. **Simple, functional, near fool-proof.** Like the art generator. No social network features, no feeds, no gamification beyond ratings.
2. **Pre-moderation everywhere.** Nothing user-submitted appears publicly until an admin approves it. This is the single most important reliability feature given the audience size and the emotional context.
3. **Humane by design.** These are real community members putting themselves forward during a grieving period. Celebrate the top; never publicly rank the bottom.
4. **Advisory, not binding.** Site copy should make clear the audience "floats" favorites; the final decision rests with the show. This avoids drama if the ratings and the eventual pick diverge.

**Explicit non-goals (v1):** comments/discussion threads, direct messaging, video submissions, live streaming, donation processing, mobile apps, federation/social login.

---

## 2. User Roles

| Role | Capabilities |
|---|---|
| **Visitor** (no account) | Browse approved candidates, listen to demos, view episode list and aggregate ratings. Read-only. |
| **Producer** (registered) | Everything a visitor can do, plus: rate demos, rate episode appearances, report content. |
| **Candidate** | A producer who has submitted an audition. Can edit their own profile/bio, replace their demo (resets to pending), withdraw. |
| **Moderator** | Approve/reject candidates, demos, and bios; tag episodes with guest hosts; view full rankings and vote analytics; handle reports; feature candidates; **edit operational settings including the voting-eligibility delay (§4.1)**. Cannot grant roles or change scoring weights. |
| **Admin** | Everything a moderator can do, plus: ban/unban accounts, grant and revoke roles, change composite-score weights, view the audit log. |

A candidate is just a producer account with a candidate profile attached — one account type, not two.

---

## 3. Core Features

### 3.1 Accounts & Authentication

- **Email magic-link login only.** No passwords. This eliminates password reset flows, credential stuffing, and most support burden — the "fool proof" choice. (Fallback option if the builder prefers: email + password with mandatory email verification.)
- Required at signup: email, display name (shown publicly on ratings? **No** — ratings are anonymous publicly, attributed internally).
- Email verification is implicit in magic-link auth.
- **Voting eligibility gate:** accounts may not vote until N hours after creation (default **48**). Blunts drive-by brigading. **N is editable at runtime by admins and moderators — see §4.1.**
- Rate limits: signup per-IP throttling, login link requests throttled (max 3 per email per hour).
- Account deletion: self-service, anonymizes ratings rather than deleting them (preserves aggregate integrity).

### 3.2 Candidate Profiles & Demo Submission

A producer clicks "Audition" and creates a candidate profile:

- **Display/stage name** (public)
- **Bio** — plain text, ~1,500 char max. Prompt them: who are you, how long have you listened, why you.
- **Optional photo** — jpg/png/webp, max 5 MB, server-side resized to standard dimensions.
- **Demo tape** — `.mp3` only:
  - Max file size: **50 MB**
  - Max duration: **15 minutes** (validated server-side via ffprobe; reject longer with a friendly error)
  - Server strips/normalizes ID3 tags; store original + a transcoded streaming copy (mono/stereo 128 kbps MP3) to keep bandwidth predictable
- Submission enters **`pending`** state. Admin approves → **`live`**, or rejects with an optional canned reason (emailed to the candidate).
- Candidate may replace their demo at any time; replacement returns to `pending` and the old ratings are archived (new demo = new rating slate — keeps it fair).
- One active candidate profile per account.
- Candidate statuses: `pending`, `live`, `rejected`, `withdrawn`, `banned`, and admin-set flags: `guest_host` (has appeared on the show), `featured`.

**Implementation notes (settled 2026-08-20, Phase 3):**

- **A live candidate's edits do not un-publish their profile.** Pre-moderation is enforced by splitting the columns, not by flipping the status: `stage_name`/`bio`/`photo_path` hold the *approved* copy and are the only fields a public template reads, while a live candidate's edits land in `pending_*` columns until a moderator promotes them. Sending a live candidate back to `pending` for a typo fix would remove their page from the site for hours and would hand any candidate a way to pull their own profile down mid-rating. Candidates who aren't live yet have no approved copy to protect, so their edits go straight to the main fields and reset the status to `pending`.
- **The slug is assigned once, at creation, and never re-derived from the stage name.** `/candidates/:slug` is a link people paste into chats and show notes; deriving it from an editable field means a rename silently breaks every existing one. Only a moderator can change it afterwards.
- **The stored original is never served.** Only the transcoded stream copy is stripped of metadata (`-map_metadata -1`), so the original still carries whatever ID3 tags — often a real name — the uploader's machine wrote. Originals live under a `private/` key prefix and appear in no template. See the Cloudflare rule in A.4.
- **`guest_host` is derived, not stored.** §5's data model has no column for it and Phase 4's `Appearance` rows answer the same question exactly; a hand-set boolean alongside them would eventually disagree. `featured` *is* stored, because nothing derives it.
- **Uploads are capped at 5 per account per day.** Rate limits are otherwise a Phase 5 item (§8), but this is the first authenticated endpoint that accepts 50 MB and starts an ffmpeg process, so the cap ships with it.

### 3.3 Demo Ratings

- Registered, vote-eligible producers rate each demo **1–5 stars**.
- **One rating per account per demo.** Rating can be changed; only the latest counts.
- No public per-user attribution. Publicly show: average (to one decimal) and vote count, only once a demo has **≥ 10 votes** (below threshold, show "Not enough ratings yet") — protects new candidates from a single 1-star looking like a verdict.
- No written reviews/comments in v1. (Biggest moderation liability for the least value.)

### 3.4 Episode List & RSS Sync

A **cron job (every 30 minutes)** fetches `https://feeds.noagendaassets.com/noagenda.xml` and upserts episodes. **The field details below were verified against the live feed on 2026-08-19** — build against these, but have Claude Code assert them at parse time rather than assume them forever.

**Field mapping (verified):**

| Field | Source | Example |
|---|---|---|
| `guid` | `<guid isPermaLink="true">` | `http://1895.noagendanotes.com` |
| `episode_number` | leading digits of `<title>` | `1895` |
| `title_raw` | `<title>` (CDATA) | `1895 - "XY You're Out"` |
| `title_display` | title with number prefix and surrounding quotes stripped | `XY You're Out` |
| `published_at` | `<pubDate>` (RFC 822) | `Sun, 16 Aug 2026 21:25:41 +0000` |
| `link_url` | `<link>` | `http://1895.noagendanotes.com` |
| `artwork_url` | per-item `<itunes:image href>` | `https://noagendaassets.com/enc/…_na-1895-art-feed.jpg` |
| `enclosure_url` | `<enclosure url>` | `https://op3.dev/e/mp3s.nashownotes.com/NA-1895-…mp3` |
| `duration_sec` | `<itunes:duration>` (already integer seconds) | `11050` |

**Parsing rules:**

- **Episode number:** `^\s*(\d+)` against the title. Store as an integer, treat as *derived/display only* — never as a key.
- **Display title:** strip the leading `NNNN - ` and any wrapping straight or curly quotes, then `.strip()`. Titles in the feed are inconsistent — at least one carries trailing whitespace inside the CDATA (`1887 - "The Stick Works" `), and quote characters vary. Store `title_raw` unmodified alongside the cleaned version so a bad cleaning rule is always recoverable without a re-sync.
- **Parse failure on any item:** log the item, skip it, continue processing the rest of the feed. Never abort the whole sync, and never delete existing rows because an item failed to parse.
- **Feed fetch failure:** log, alert after 3 consecutive failures, retry next cycle. Existing episode data is never wiped on a bad or empty fetch. Treat a feed that parses to zero items as a failure, not as "all episodes deleted."

**Three things worth building in deliberately:**

1. **Skip `<podcast:liveItem>` elements.** The feed contains a live-stream entry alongside real episodes, with `isPermaLink="false"` and a placeholder enclosure. A naive "iterate every item-like element" parser will create a phantom episode called *No Agenda Episode 1895 - Live*. Only process `<item>` children of `<channel>`.

2. **Normalize the GUID before using it as a key.** The GUID is a permalink URL (`http://NNNN.noagendanotes.com`), which means a future scheme change (`http` → `https`), a trailing slash, or a case difference would read as a brand-new episode and silently duplicate the entire back catalogue. Normalize on write and on lookup: lowercase, strip scheme, strip trailing slash. Store the normalized form in the unique index and keep the raw GUID in its own column.

3. **Do not use the `enclosure_url` for playback or hotlinking.** The enclosure is wrapped in an OP3 analytics prefix (`https://op3.dev/e/…`). Every request through that URL registers as a download in the show's own stats. A talent-search site that autoplays or prefetches episode audio would quietly corrupt the show's numbers. **Link to `link_url` (the show notes page) instead.** If a direct audio link is ever needed, strip the `https://op3.dev/e/` prefix first and document why.

**Also worth knowing:**

- **Episode floor: ingest only episodes numbered ≥ 1890.** This site covers the show's new era, and 1890 is the first regular episode of it — 1889 was the producer tribute to John and sits outside the guest-host format this site exists to support. Items below the floor are skipped silently during sync — not stored, not displayed. Implement as the runtime setting `min_episode_number` (§4.1) rather than a hardcoded constant, so the boundary can be moved without a redeploy or a migration.
  - The floor is applied **after** the number is parsed. An item whose number can't be parsed is skipped as a parse failure (logged), not treated as below the floor.
  - Because of the floor, `/episodes` is **not** a full archive and shouldn't look like a broken one. Label the page accordingly (e.g. "Episodes since the show's return") and don't paginate into emptiness below the floor.
  - If the floor is ever lowered, the next sync backfills the newly-eligible episodes automatically, provided the feed still carries them — which, per the depth note below, means back to roughly episode 1667.
- **Don't import `<description>`.** It's a large HTML blob of executive-producer credits, knighting announcements, and donor names — hundreds of lines per episode, occasionally with malformed markup. It has no use on this site and rendering it would be both ugly and a privacy own-goal. Skip the field entirely.
- **Publish days aren't reliable.** The show is nominally Thursday/Sunday, but the feed shows episodes landing on a Friday (1888) and a Monday (1889). Never infer anything from day-of-week.
- **Feed depth — ANSWERED (2026-08-20):** the feed is a **rolling window of 230 items** (episodes 1667–1896 at time of checking), not the full back catalogue. The site will only ever know about recent episodes — fine here, since appearances are all forward-looking — and `/episodes` says so rather than appearing to be a broken archive. Two consequences the sync respects: an episode dropping out of the window is never treated as a deletion, and lowering `min_episode_number` only backfills as deep as the window still reaches.
- **The feed declares guest hosts, and its `host` role is stale — verified 2026-08-20.** Items carry `<podcast:person>` elements. `role="guest host"` is hand-curated and reliable (Rob Dew on 1896 was the only one at time of checking). `role="host"` is a boilerplate template value: John C Dvorak is listed on 229 of 230 items, including 1889 — the producer tribute to him — and every episode published since. **Ingest and display `role="guest host"` only; never render anything from `role="host"`.**
- The site does **not** host or rehost episode audio.
- Episodes display newest-first with artwork, cleaned title, episode number, and date.

### 3.5 Guest Host Appearances & Episode Ratings

- Admins **tag an episode with one or more candidates** who guest-hosted it (appearance records). Optional admin note per appearance (e.g., "Sunday rotation, full episode").
- Producers rate **each appearance** (candidate × episode) 1–5 stars, same rules as demo ratings (one per account, changeable, 10-vote display threshold).
- **Rating window:** appearances are rateable from the moment the admin tags them until **14 days after** the episode's publish date (configurable). Prevents ancient appearances from being brigaded later.
- Appearance pages show: episode info, the candidate, aggregate rating, and links to the candidate's profile and demo.

### 3.6 Leaderboard ("Community Favorites")

- Public page showing **only the top N (default 10)** candidates by composite score. **Never display a full ranked list publicly.** Full rankings live in the admin panel.
- Candidates with no on-show appearance yet are excluded from the main leaderboard and appear in a separate **"Rising Demos"** list (top 10 by smoothed demo score) so the funnel stays visible.
- Leaderboard recomputed hourly by a cron job into denormalized columns, not on page load.

**Exact scoring.** Implement as one pure, unit-tested function. Three levels, all using the same smoothing helper:

```
smooth(R, v, m, C) = (v/(v+m))·R + (m/(v+m))·C
    R = raw mean stars for this item
    v = number of votes on this item
    m = smoothing constant (pulls low-vote items toward the mean)
    C = prior (the site-wide mean it gets pulled toward)
```

1. **Demo score** — `smooth(R_demo, v_demo, m=10, C=C_demos)`
2. **Appearance score** — each appearance is smoothed individually with `m=5`, `C=C_appearances`, then averaged across the candidate's appearances (unweighted; a candidate with four appearances isn't penalized for one weak night, and each night still counts).
3. **Composite** — `0.7 · appearance_score + 0.3 · demo_score`

- **`C` (the priors)** are the site-wide mean star ratings across all live demos and all appearances respectively, recomputed in the same hourly job. Before any ratings exist, seed both at **3.5** to avoid a divide-by-zero and a nonsense cold start.
- **`m` values** are deliberately different: demos accumulate votes slowly and are lower-stakes, so `m=10` matches the display threshold; appearances get a burst of votes right after an episode, so `m=5` lets a genuinely strong showing surface within a couple of days.
- **Use shrinkage, not a hard cutoff, at the appearance level.** Requiring e.g. 10 votes before an appearance counts creates a cliff: an appearance with 9 votes contributes nothing, and the same appearance at 10 votes suddenly contributes fully. Smoothing handles thin data continuously — a 2-vote appearance barely moves the candidate's score instead of being discarded or dominating it.
- The composite is computed for `live` candidates only. Withdrawn, rejected, and banned candidates are skipped in the job but their historical rows are retained for admin analytics.
- **Display threshold and scoring threshold are separate concerns.** `min_votes_to_display` (default 10) governs whether a public average is shown at all; the smoothing constants govern ranking math. Don't conflate them in code.

### 3.7 Reporting & Abuse

- "Report" button on candidate profiles/demos (reasons: impersonation, offensive content, spam, other). Reports queue in admin panel; auto-hide only at a high threshold (e.g., 10 unique reports) pending review.
- Admin ban: soft-deletes the account's ratings from aggregates and hides their candidate profile.

---

## 4. Admin Panel

Single `/admin` area, role-gated. Needs:

1. **Moderation queue** — pending candidates/demos/bio edits with inline audio player, approve/reject with canned reasons.
2. **Episode manager** — synced episode list; attach/detach candidate appearances; trigger manual RSS re-sync.
3. **Full rankings & analytics** — complete leaderboard, raw vs. Bayesian scores, vote velocity per candidate (spikes = possible brigading), votes-per-account distribution.
4. **User management** — search, view rating history, ban/unban, grant admin.
5. **Reports queue.**
6. **Settings** — see §4.1.
7. **Audit log** of admin actions (who approved/banned/edited what, when).

### 4.1 Runtime Settings

All values below live in the `settings` table and are **editable from the admin UI without a redeploy**. Environment variables (§A.5) supply the initial values on first boot only; after that, the database is the source of truth. Claude Code should implement a single `get_setting(key)` helper with a short in-process cache (60s TTL) — no setting should be read directly from the environment at request time.

| Setting | Default | Range | Who can edit |
|---|---|---|---|
| `vote_eligibility_hours` | 48 | 0–336 | Moderator, Admin |
| `min_votes_to_display` | 10 | 1–100 | Moderator, Admin |
| `appearance_rating_window_days` | 14 | 1–90 | Moderator, Admin |
| `demo_max_duration_sec` | 900 | 60–3600 | Moderator, Admin |
| `demo_max_file_mb` | 50 | 5–200 | Moderator, Admin |
| `leaderboard_size` | 10 | 3–50 | Moderator, Admin |
| `score_weight_appearance` | 0.7 | 0–1 | **Admin only** |
| `score_weight_demo` | 0.3 | 0–1 | **Admin only** |
| `auditions_open` | true | bool | Moderator, Admin |
| `min_episode_number` | 1890 | 1–99999 | **Admin only** |

**Voting-eligibility delay — implementation notes.** This one has enough sharp edges to be worth specifying precisely:

- **Compute eligibility dynamically, don't freeze it at signup.** A user may vote when
  `now() >= COALESCE(users.vote_eligible_override_at, users.created_at + vote_eligibility_hours)`.
  Storing a fixed `vote_eligible_at` timestamp at registration would mean a settings change only affects *future* signups — which defeats the purpose of the control, since the reason to reach for it is almost always a problem happening right now with accounts that already exist.
- **Lowering the value takes effect immediately** for everyone currently waiting. Raising it likewise re-gates accounts that hadn't yet voted.
- **Never retroactively invalidate votes already cast.** Raising the delay stops future votes from newly-ineligible accounts; it does not delete their existing ratings. If a moderator needs to remove votes after a brigading incident, that's a separate, deliberate admin action with its own audit entry — not a side effect of changing a number in a settings form.
- **`0` disables the gate entirely.** Useful during the trusted-producer beta (§A.9 step 2). The UI should warn when saving 0.
- **Per-account override.** Admins can grant an individual account immediate eligibility by setting `vote_eligible_override_at`. This is the escape hatch for "a known producer emailed hello@ because they can't rate the demo their friend just posted" — better than dropping the global gate for one person.
- **The admin UI should show the blast radius before saving:** "N accounts are currently within the waiting period. Changing 48 → 12 will immediately make M of them eligible to vote." A confirmation step on a change this consequential is worth the extra click.
- **Every change writes an audit-log entry** recording the actor, old value, new value, and timestamp.
- **Surface it where it's needed.** Put a compact control for this setting on the moderation-queue and vote-analytics screens, not buried three clicks deep in Settings — the moment you want to raise it is the moment you're staring at a suspicious vote-velocity spike.
- **Public-facing copy must read the live value.** The About page and signup screens currently hardcode "48 hours" (see the About copy doc). Render that number from the setting so the site never contradicts itself.

---

## 5. Data Model (suggested)

```
users            id, email (unique), display_name,
                 role (producer|moderator|admin),
                 created_at, email_verified_at, banned_at,
                 vote_eligible_override_at  -- NULL normally; set only for
                                            -- manual early grants (see §4.1)

candidates       id, user_id (unique FK), stage_name, bio, photo_path,
                 status (pending|live|rejected|withdrawn|banned),
                 is_featured, created_at, approved_at

demos            id, candidate_id, original_path, stream_path, duration_sec,
                 file_size, status (pending|live|rejected|archived), created_at

episodes         id, guid (unique), episode_number, title, published_at,
                 link_url, artwork_url, enclosure_url, duration_sec, synced_at

appearances      id, episode_id, candidate_id, admin_note,
                 rateable_until, created_at
                 UNIQUE(episode_id, candidate_id)

ratings          id, user_id, rateable_type (demo|appearance), rateable_id,
                 stars (1–5), created_at, updated_at
                 UNIQUE(user_id, rateable_type, rateable_id)

reports          id, reporter_user_id, target_type, target_id, reason,
                 details, status (open|resolved|dismissed), created_at

magic_links      id, user_id, token_hash, expires_at, used_at

admin_audit_log  id, admin_user_id, action, target_type, target_id,
                 metadata_json, created_at

settings         key, value_json
```

Aggregates (avg stars, vote counts, composite scores) can be denormalized into `candidates`/`demos`/`appearances` columns updated by the scoring job.

---

## 6. Pages / Routes

**Public:**
- `/` — Home: mission statement, top favorites, latest guest-host episodes, "Audition" CTA
- `/candidates` — Approved candidates (sort: newest, name, top demos)
- `/candidates/:slug` — Profile: bio, photo, demo player, appearance history with ratings
- `/episodes` — Synced episode list; guest-hosted episodes badged
- `/episodes/:number` — Episode detail + appearance rating widgets
- `/leaderboard` — Community favorites (top N) + Rising demos
- `/about` — How this works, how the pick will be made, house rules
- `/login`, `/signup`

**Authenticated:**
- `/audition` — Create/edit candidate profile & upload demo
- `/account` — Email, display name, delete account

**Admin:** `/admin/...` per Section 4.

---

## 7. Technical Recommendations

Chosen for one-producer maintainability, not resume-driven engineering.

- **Stack:** A single server-rendered web app. Good options Claude Code handles well: **Next.js (App Router) with server actions**, or **Flask/Django**, or **SvelteKit**. Pick one; avoid a separate SPA + API.
- **Database: SQLite** (with Litestream or nightly dumps for backup). Write volume here is tiny — ratings and signups — and SQLite removes an entire service to operate. Postgres is fine if the host provides it managed.
- **File storage:** S3-compatible object storage (Cloudflare R2 or Backblaze B2) for mp3s and photos. **Do not store uploads on the app server's disk.** Serve demo audio via the CDN.
- **Audio processing:** `ffmpeg/ffprobe` on upload — validate it's really an MP3, enforce duration, transcode the streaming copy. Process asynchronously (simple job queue or an in-process worker) so uploads don't block.
- **Email:** Transactional provider (Postmark, Resend, SES) for magic links and moderation notices. At this scale, cost is trivial.
- **Edge/CDN:** Cloudflare in front for caching, TLS, and DDoS protection. Cache public pages aggressively (60s is plenty); ratings don't need real-time freshness.
- **Anti-bot:** Cloudflare Turnstile on signup and demo upload.
- **Hosting:** One small VPS (Hetzner/DigitalOcean, 2 vCPU / 4 GB) or a PaaS (Fly.io/Railway). Docker Compose for reproducibility.
- **Monitoring:** Uptime ping + error tracking (Sentry free tier) + a daily admin digest email (new signups, pending queue size, RSS sync health).

**Scale assumptions:** 1–1.5 M listeners → realistic participation of ~10–50 k accounts, low hundreds of candidates, a few thousand ratings/day at peak (post-episode). The demo *audio bandwidth* is the only real load, and the CDN absorbs it. This stack is comfortably 10× overprovisioned.

---

## 8. Security & Integrity Checklist

- One vote per account per item, enforced by DB unique constraint (not just app logic)
- Voting-eligibility delay for new accounts (default 48h, moderator-adjustable at runtime per §4.1 — raise it as a live lever during a brigading incident)
- Per-IP and per-account rate limits on signup, login links, uploads, and rating submissions
- Magic-link tokens: single-use, 15-minute expiry, hashed at rest
- All uploads validated server-side (magic bytes, ffprobe), never trusted by extension
- Admin routes behind role check + (optional) IP allowlist or second factor
- Vote-velocity anomaly flagging in admin analytics (brigade detection)
- GDPR-ish hygiene: minimal PII (email only), self-service deletion, no trackers

---

## 9. Build Phases (for Claude Code)

**Phase 1 — Foundation:** Project scaffold, DB schema + migrations, magic-link auth, account pages, admin role.

**Phase 2 — RSS sync:** Feed fetcher + cron, episode list pages. (Independent of everything else — good early win with real data on screen.)

**Phase 3 — Auditions:** Candidate profile CRUD, mp3 upload pipeline (validate → transcode → object storage), moderation queue, public candidate pages with audio player.

**Phase 4 — Ratings:** Demo ratings, appearance tagging (admin), appearance ratings, Bayesian scoring job, leaderboard + Rising Demos.

**Phase 5 — Hardening:** Reports, rate limits, Turnstile, vote-velocity analytics, audit log, admin digest email, backups, deploy.

Each phase should end deployable. Ask Claude Code to write tests for: the scoring function, vote uniqueness, upload validation, and RSS idempotency — the four places silent bugs would hurt most.

---

## 10. Content & Tone Notes (for site copy)

- The About page should acknowledge the moment plainly and frame the site as the community carrying the show forward — in its own tradition of producers contributing — not as a replacement contest. Copy to be written by the production team, not generated.
- House rules: be constructive, rate the performance not the person, remember candidates are fellow producers.
- Make explicit: ratings inform the show's decision; they don't decide it.

---

## 11. Decisions (formerly Open Questions) — RESOLVED

1. **Candidate stats visibility:** Candidates see their own averages only once past the 10-vote threshold; individual votes are never shown to anyone but admins.
2. **Appearance treatment:** Uniform for all episodes regardless of day. No schema assumptions about which day guests appear — the schedule may change. The admin note field distinguishes context when useful.
3. **Rating scale:** 1–5 stars, as specced.
4. **Audition window:** Rolling submissions, no deadline. (A "Season 1" framing with a soft deadline is available later as a marketing move; requires no schema change.)
5. **Moderation email:** hello@noagendatalentsearch.com — set up and monitored by the producer. Inbound: use Cloudflare Email Routing (free) to forward to a personal inbox. Outbound transactional mail: Resend or Postmark with SPF/DKIM configured on the domain.

## 12. Hosting & Domain (decided direction)

- **Domain registration + DNS:** Cloudflare Registrar (at-cost pricing) — keeps registration, DNS, CDN/caching, Turnstile, R2 storage, and email forwarding in one dashboard.
- **App hosting:** A managed PaaS rather than a VPS, given no dedicated-server ops background: **Render** or **Railway**, deploying straight from a GitHub repo with automatic HTTPS, cron jobs, and one-click managed **Postgres**.
- **Database note:** On a PaaS, use the platform's managed Postgres instead of SQLite (PaaS filesystems are ephemeral; a managed DB with automatic backups is the fool-proof option there). SQLite remains the recommendation only if a VPS is chosen instead.
- **Object storage:** Cloudflare R2 for demo mp3s and photos (no egress fees, pairs with the CDN).
- Keep Bluehost for existing sites; don't try to run this app there — shared PHP hosting can't run the worker/cron/ffmpeg pipeline this needs.

---

# Appendix A — Deployment Checklist

Ordered setup guide. Steps 1–4 are producer tasks (accounts, DNS, credentials). Steps 5–8 are for Claude Code. Do steps 1–4 first so the credentials exist before the app needs them.

## A.1 Domain & DNS (Cloudflare)

- [x] Create a Cloudflare account.
- [x] Register **noagendatalentsearch.com** via Cloudflare Registrar (at-cost, ~$10–12/yr). DNS is configured automatically.
- [x] Enable **Always Use HTTPS** and set SSL/TLS mode to **Full (strict)**.
- [x] Under Security → Turnstile, create a widget for the domain. Save the **site key** (public) and **secret key** (private).
- [x] Leave DNS records alone for now — the host will supply the target in A.3.

## A.2 Email

**Inbound (hello@noagendatalentsearch.com):**
- [x] Cloudflare dashboard → Email → **Email Routing** → enable.
- [x] Add a custom address `hello@noagendatalentsearch.com` forwarding to the producer's monitored inbox.
- [x] Verify the destination address (Cloudflare sends a confirmation email).
- [x] Cloudflare adds the MX and SPF records automatically — accept them.

**Outbound (magic links, moderation notices):** still outstanding as of 2026-08-20. App-side wiring is ready and waiting (`RESEND_API_KEY` set → `config/settings.py` switches from console-log backend to Resend's SMTP relay automatically, no redeploy needed beyond setting the var) — nothing below is done yet.
- [x] Create a **Resend** account (free tier covers ~3,000 emails/month; upgrade later as signups grow).
- [x] Add and verify the domain in Resend; add the DKIM and SPF records it provides to Cloudflare DNS.
- [x] Set the sending identity to `No Agenda Talent Search <hello@noagendatalentsearch.com>`.
- [x] Generate an API key. Save it.
- [ ] **Warning:** magic-link auth means email deliverability *is* login. Verify DKIM/SPF pass before launch (send a test to Gmail, Outlook, Yahoo, and Proton and check each lands in the inbox, not spam).

## A.3 App Hosting (Render)

- [x] Create a Render account, connect it to GitHub.
- [x] Create a **Web Service** from the repo (Claude Code will provide a Dockerfile — use Docker runtime so `ffmpeg` is available).
- [x] Create a **Render Postgres** instance (starter tier is plenty). Copy the internal connection string.
**The web service and Postgres were created by hand, not from a Blueprint** (the
live service is named `noagenda-talentsearch`). So `render.yaml` has never been
applied and is documentation only: env var changes made there — `ALLOWED_HOSTS`,
for one — must also be set on the service in the dashboard, and the cron jobs
below have to be created by hand. Adopting the Blueprint later is an open
decision; it may create duplicate services rather than take over the running
one, which would mean moving the custom domain and reissuing its certificate.

- [x] Create two **Cron Jobs** by hand (Docker runtime, same repo). Each is a
      separate container and inherits nothing from the web service, so both need
      `DATABASE_URL` (the same Postgres), a matching `SECRET_KEY`, and
      `APP_ENV=production`:
  - `rss-sync` — every 30 min (`*/30 * * * *`), `python manage.py rss_sync`. Also
    needs `RSS_FEED_URL`. Confirmed running: production lists episodes from 1890 up.
  - `process-demos` — every 15 min (`*/15 * * * *`), `python manage.py process_demos`.
    Also needs all five `R2_*` vars — miss one and it silently writes transcoded
    audio to a cron container's disk, which is discarded when the job exits. The
    transcode backstop, not the normal path: uploads transcode immediately in a
    background thread, and this only picks up what a deploy or crash abandoned.
  - `recompute-scores` — hourly (`0 * * * *`), `python manage.py recompute_scores`.
    **Create this in the dashboard when Phase 4 lands** (same as the other two:
    the Blueprint is not the live source of truth). Needs `DATABASE_URL`,
    `SECRET_KEY`, `APP_ENV=production`. The job writes denormalized scores;
    page loads never compute them. A successful rating or appearance tag also
    runs it in-process, so the cron is the backstop for bans and settings changes.
- [x] Add the custom domain `noagendatalentsearch.com` in Render; it will supply a CNAME/A target to add in Cloudflare DNS.
- [x] In Cloudflare, add that record with proxy **enabled** (orange cloud).
- [x] Enable **auto-deploy on push to `main`**.

## A.4 Object Storage (Cloudflare R2)

- [x] Create an R2 bucket: `nats-media`.
- [x] Create an **R2 API token** scoped to that bucket (Object Read & Write). Save the access key ID, secret, and account ID.
- [x] Connect a public custom domain for reads: `media.noagendatalentsearch.com`.
- [x] Bucket CORS policy — **not required, deliberately skipped.** CORS governs
      cross-origin requests made by *scripts*; this site has no JavaScript at all
      and plays demos with plain `<audio src>` elements, which are not subject to
      it. Uploads are server-side, so a browser never talks to R2 directly.
      Revisit only if something like a waveform display or Web Audio is added.
- [ ] Confirm uploads go *only* through the app (signed server-side); the public domain is read-only.
- [x] **Block `/private/*` on `media.noagendatalentsearch.com`** with a Cloudflare rule. The app writes original uploads under a `private/` key prefix and never links to them, but an R2 custom domain serves the whole bucket — and unlike the streaming copy, the original still carries the uploader's ID3 tags. The keys are UUIDs so nothing is enumerable, but this is the belt to that braces.
- [x] Set the five `R2_*` variables on **both** the web service and the `process-demos` cron. The app falls back to local disk if any one of them is missing, which on Render means uploads disappear at the next deploy — set them before auditions open, not after.

## A.5 Environment Variables

Claude Code should read all of these from the environment and fail loudly at boot if any are missing. Never commit them.

```
# Core
APP_ENV=production
APP_URL=https://noagendatalentsearch.com
SECRET_KEY=<generate 64 random chars>
DATABASE_URL=<Render Postgres internal connection string>

# Email
RESEND_API_KEY=<from A.2>
MAIL_FROM="No Agenda Talent Search <hello@noagendatalentsearch.com>"
ADMIN_NOTIFY_EMAIL=hello@noagendatalentsearch.com

# Storage (R2)
R2_ACCOUNT_ID=<...>
R2_ACCESS_KEY_ID=<...>
R2_SECRET_ACCESS_KEY=<...>
R2_BUCKET=nats-media
R2_PUBLIC_BASE_URL=https://media.noagendatalentsearch.com

# Anti-bot
TURNSTILE_SITE_KEY=<...>
TURNSTILE_SECRET_KEY=<...>

# Feed
RSS_FEED_URL=https://feeds.noagendaassets.com/noagenda.xml
MIN_EPISODE_NUMBER=1890

# Monitoring
SENTRY_DSN=<optional>

# First-boot seed values ONLY — after initial migration the `settings`
# table is the source of truth and these are ignored. Do not read them
# at request time. See §4.1.
VOTE_ELIGIBILITY_HOURS=48
MIN_VOTES_TO_DISPLAY=10
APPEARANCE_RATING_WINDOW_DAYS=14
DEMO_MAX_DURATION_SEC=900
DEMO_MAX_FILE_MB=50
LEADERBOARD_SIZE=10
SCORE_WEIGHT_APPEARANCE=0.7
SCORE_WEIGHT_DEMO=0.3
```

## A.6 Repository Setup (Claude Code)

- [x] Initialize repo with `.gitignore` covering `.env`, uploads, and build artifacts.
- [x] Commit a `.env.example` listing every variable above with placeholder values.
- [x] Dockerfile installs `ffmpeg` (needed for `ffprobe` validation and transcoding).
- [ ] Add `render.yaml` (Render Blueprint) declaring the web service, Postgres, and both cron jobs so the infrastructure is reproducible. **Partial:** web service + Postgres + `rss-sync`, `process-demos`, and `recompute-scores` are declared in the file; adopting the Blueprint is still an open decision, so the live crons are created by hand in the dashboard.
- [x] Add a `/healthz` endpoint returning app + DB status.
- [x] Migrations run automatically on deploy (via `render.yaml`'s `preDeployCommand`).
- [x] Add a seed/CLI command to promote a user to admin by email (`manage.py make_admin <email>`) — needed to bootstrap the first admin account.

## A.7 Pre-Launch Smoke Test

Run through this on the live domain before announcing anything:

- [ ] Sign up with a fresh email → magic link arrives in **inbox**, not spam → login works.
- [ ] Magic link is single-use and expires (try reusing it).
- [ ] Voting is blocked for a brand-new account and allowed once the eligibility window passes.
- [ ] Change `vote_eligibility_hours` in the admin UI from 48 to 0 → an account created moments ago becomes eligible **immediately**, with no redeploy and no re-login. Set it back to 48 → that same account is gated again. This confirms eligibility is computed dynamically rather than frozen at signup (§4.1).
- [ ] Raising the delay does **not** delete votes already cast by accounts that are now gated.
- [ ] A moderator account can change the eligibility delay; a moderator account **cannot** change score weights or grant roles.
- [ ] The change appears in the audit log with old value, new value, and actor.
- [ ] The "48 hours" figure shown on the About/signup pages updates to match the new setting.
- [ ] Upload a valid 10-minute MP3 → lands in `pending`, transcodes, plays back correctly from the R2 public domain.
- [ ] Upload a 20-minute MP3 → rejected with a clear message.
- [ ] Upload a `.wav` renamed to `.mp3` → rejected by content inspection, not extension.
- [ ] Approve a demo in admin → appears publicly.
- [ ] Rate a demo twice from the same account → single rating updated, not duplicated. Verify the DB unique constraint by attempting a direct duplicate insert.
- [ ] Ratings hidden below 10 votes; average appears at 10.
- [ ] Trigger RSS sync manually → episodes populate. Run it twice → no duplicates.
- [ ] Episodes numbered below 1890 are absent; 1890 ("Flock Off!") is the oldest episode on `/episodes`, and 1889 is NOT present.
- [ ] The live-stream entry (`podcast:liveItem`) did NOT create a phantom episode.
- [ ] No episode row stores the `<description>` blob.
- [ ] Lower `min_episode_number` by 10, re-sync → older episodes backfill; raise it back → they disappear from public view without erroring.
- [ ] Tag an episode with a guest host → appearance rating widget appears and closes after the rating window.
- [ ] Leaderboard recomputes and reflects the Bayesian formula, not raw averages.
- [ ] Report a candidate → appears in the admin queue.
- [ ] Test on mobile — a large share of the audience will be on phones.
- [ ] Confirm Turnstile blocks a scripted signup attempt.

## A.8 Backups & Monitoring

- [ ] Confirm Render Postgres daily backups are enabled; note the retention window.
- [ ] Schedule an additional weekly `pg_dump` to R2 (a cron job) — platform backups are not a backup strategy on their own.
- [ ] **Test a restore once** into a scratch database before launch.
- [ ] Add an uptime monitor (UptimeRobot free tier) hitting `/healthz` every 5 minutes, alerting the producer's email/phone.
- [ ] Sentry project created, DSN set, a test error confirmed as received.
- [ ] Daily admin digest email: new signups, pending moderation count, RSS sync status, vote-velocity anomalies.

## A.9 Launch Sequence

1. Deploy quietly and leave the site up, unannounced, for 48 hours. Watch logs.
2. Invite ~10 trusted producers to sign up, submit a demo, and rate. Fix what breaks.
3. Confirm the moderation queue workflow feels sustainable for one person at low volume, and recruit 2–3 volunteer moderators **before** the announcement, not after.
4. Announce on-air and in the newsletter. Expect the largest traffic spike the site will ever see in the first 6 hours — check R2 bandwidth and Postgres connection counts during it.
5. Hold the first week's approvals to a slightly higher bar; the tone of the first twenty published demos sets the tone for everything after.

## A.10 Running Cost Estimate

| Item | Monthly |
|---|---|
| Domain (amortized) | ~$1 |
| Render web service (Starter) | ~$7 |
| Render Postgres (Basic) | ~$7 |
| Cloudflare (DNS, CDN, Turnstile, Email Routing) | $0 |
| R2 storage (~50 GB of demos) | ~$1 |
| R2 egress | $0 |
| Resend (free tier → paid at scale) | $0–20 |
| Sentry / UptimeRobot free tiers | $0 |
| **Total** | **~$16–36/mo** |

Scale up the Render instance only if response times degrade during post-episode traffic spikes — the CDN absorbs most of it.

---

# Appendix B — Implementation Details

Decisions that were previously left implicit. Each is a default Claude Code should follow unless told otherwise.

## B.1 Candidate Slugs & Profiles

- **Slug** = `slugify(stage_name)`, ASCII-folded, lowercased, non-alphanumerics collapsed to single hyphens, trimmed to 60 chars. On collision, append `-2`, `-3`, … Uniqueness enforced by DB constraint, not application logic alone.
- **Reserve a blocklist** so a candidate can't take `admin`, `about`, `login`, `leaderboard`, `episodes`, `candidates`, `audition`, `account`, `api`, `healthz`.
- This audience's naming conventions will stress the slugifier harder than most — stage names in this community routinely run long, carry titles and honorifics, and include punctuation, `&`, and non-ASCII characters. Test the slugifier against genuinely adversarial examples before launch, not against `John Smith`.
- **DECIDED: slugs are generated from the stage name, not chosen by the candidate, and are frozen at approval.** If a candidate edits their stage name later, the display name updates and the URL does not — a changing slug breaks every link the community has already shared. Admins can force a slug change manually if someone has a good reason; it 301-redirects from the old one.
- **Withdrawn / rejected / banned:** profile returns 404 publicly and the slug stays reserved (prevents a banned account's URL being re-registered by someone else). Ratings rows are retained for admin analytics but excluded from all public aggregates and from the scoring job.
- **Photo:** resized server-side to a 512×512 center-cropped square (WebP, quality 82), plus a 128×128 thumbnail. Strip EXIF — it can carry GPS coordinates, and these are private individuals. No photo uploaded → render a generated monogram avatar from the stage name; do not ship a stock silhouette.

## B.2 Demo Replacement & Archival

- Replacing a demo sets the previous row to `status = archived` and inserts a new `pending` row. Ratings stay attached to the archived demo's ID permanently.
- **DECIDED: the public profile shows only the current `live` demo.** Archived demos are admin-visible only — a candidate who re-recorded shouldn't have their first attempt permanently on display. There is no public demo history and no "previous versions" UI.
- The candidate's demo score is computed from the current live demo only. Archived-demo ratings never feed the composite.
- If a replacement demo is rejected, the previously live demo is **restored to live** rather than leaving the candidate with nothing public. This is easy to get wrong and very visible when it goes wrong.

## B.3 Auth & Session Details

- **Session lifetime: 90 days (decided), sliding** — each request refreshes the window. Long sessions are correct here — asking a producer to re-authenticate by email every two weeks converts a rating into a chore, and the threat model is brigading, not account compromise of a low-value profile.
- **Session cookie:** HttpOnly, Secure, SameSite=Lax.
- **Magic link:** single-use, 15-minute expiry, token hashed at rest, invalidated on use.
- **Expired or already-used link** → a friendly page explaining the link expired, with a one-click "send me a new one" form pre-filled with nothing (never echo the email address from the URL). Not a raw 403.
- **Rate limits, pinned:** 3 link requests per email address per hour; 10 per IP per hour; 30 rating submissions per account per minute (generous — the point is to stop scripts, not fast raters); 5 signups per IP per day; 3 demo uploads per account per day.
- **Always respond identically** whether or not the email address exists. No account enumeration.
- **Logout** clears the session server-side, not just the cookie. No "remember this device" feature — the 90-day session already is one.

## B.4 Upload Pipeline

- **Durable, DB-backed job queue.** A `jobs` table with `status`, `attempts`, `locked_at`, `last_error`, polled by a worker. At this volume there is no reason to add Redis or Celery. Requirements: a crash mid-transcode leaves the row in `processing` with a stale `locked_at`, and a reaper re-queues anything locked for more than 15 minutes. Max 3 attempts, then `failed` with an admin alert.
- **Validation order** (fail fast, cheapest first): size → magic bytes → `ffprobe` → duration.
- **Retain the original file.** At ~50 MB max and a few hundred candidates, worst case is roughly 25 GB — about $0.38/month on R2. There is no cost argument for discarding the source, and having it means a bad transcode is always recoverable.
- **Exact user-facing rejection messages** (write them once, reuse them; vague upload errors generate support email):
  - Too large: *"That file is over the 50 MB limit. Try exporting at a lower bitrate — 128 kbps mono is plenty for a demo."*
  - Not an MP3: *"That doesn't look like an MP3 file. If you exported a .wav or .m4a, convert it to MP3 and try again."* (Triggered by content inspection, not the file extension.)
  - Too long: *"Demos are capped at 15 minutes — yours is 18:22. Tighter is better anyway; cut it to your strongest segment."*
  - Unreadable: *"We couldn't read that audio file — it may be corrupted. Try re-exporting it."*
  - Processing failed after upload: email the candidate, don't leave the profile silently stuck in `pending`.

## B.5 Lists, Empty States & Copy

- **`/candidates`** — 24 per page, default sort **newest approved first** (gives every new candidate a moment at the top; sorting by rating by default would entrench early leaders). Alternate sorts: top-rated, alphabetical.
- **`/episodes`** — 20 per page, newest first. Badge episodes that have tagged guest-host appearances.
- **Empty states are not optional** — the site launches completely empty and the first visitors are the ones you most want to convert:
  - No candidates: *"No auditions yet. Be the first."* + audition CTA.
  - No guest hosts tagged on an episode: *"No guest host on this one."*
  - Leaderboard with no appearances yet: show Rising Demos only, with a line explaining the main board fills in once guest hosts start appearing on the show.
  - Below display threshold: *"Not enough ratings yet"* — never render `0.0` or an empty star row, which reads as a bad score rather than as missing data.
  - Rating window closed: *"Ratings for this appearance are closed."* with the final average still shown.
- **Candidates see their own averages** once past the display threshold, and never individual votes or voter identities. Below threshold they see the same "not enough ratings yet" as everyone else.
- **Mobile-first layout.** Most of this audience will be on a phone, often listening while browsing. The audio player and the star control are the two elements that must be comfortable one-handed.
- Real `404` and `500` pages in the show's voice, not framework defaults.

## B.6 Stack

Either of these is a good answer; the important constraint is **one server-rendered app, no separate SPA + API**:

- **Django + Postgres** — my mild preference. The two things most likely to cause trouble here are the ffmpeg pipeline and the durable job queue, and both are more natural in Python. Django's admin also gives you most of Section 4 for free, which is a meaningful chunk of the build.
- **Next.js (App Router) + server actions + Postgres** — equally viable and very well-trodden with Claude Code. Note that the background worker is a separate process either way; server actions don't remove that requirement.

Pick based on which one you'd rather debug at 11pm, and tell Claude Code the choice explicitly in the first prompt rather than letting it pick.
