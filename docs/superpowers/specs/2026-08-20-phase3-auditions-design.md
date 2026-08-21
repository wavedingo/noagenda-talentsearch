# Phase 3 — Auditions: Design

**Status:** Approved
**Source spec:** `specs/noagendatalentsearch-spec.md` (§3.2, §4, §6, §7, §8, §9 Phase 3, A.4, A.5, A.7)
**Scope:** Candidate profile CRUD, the mp3 upload pipeline (validate → transcode → object storage), the moderation queue, and public candidate pages with an audio player. No ratings, no scores, no leaderboard — those are Phase 4.

## Decisions

1. **Pre-moderation is a schema property, not a status check.** Principle #2 says nothing user-submitted appears publicly until approved. The naive reading — send a live candidate back to `pending` when they fix a typo — makes their profile vanish from the site for hours and hands any candidate a way to yank their own page mid-rating. Instead, `stage_name`/`bio`/`photo_path` hold the **approved** copy and are the only fields any public template reads; a live candidate's edits land in `pending_stage_name`/`pending_bio`/`pending_photo_path` and the public page keeps showing the approved version until a moderator promotes the draft. A candidate who is not yet live has no approved copy to protect, so their edits go straight to the main fields and reset the status to `pending`. One rule, two cases, no window in which unapproved text is public.

2. **The slug is assigned once and never tracks the stage name.** `/candidates/:slug` is a URL people paste into shows and chats. Deriving it from an editable, re-moderatable field means a rename silently breaks every existing link. The slug is generated from the stage name at creation, de-duplicated with a numeric suffix, and thereafter only a moderator can change it in Django admin. It is not public until the candidate is approved, so an abusive stage name never surfaces as a URL — it just gets rejected.

3. **Validate synchronously, transcode in the background.** Split because the two halves have opposite requirements. Validation must be immediate: A.7 expects a 20-minute file and a `.wav` renamed to `.mp3` to come back with a clear error while the user is still looking at the form. `ffprobe` only reads headers, so that costs well under a second even on a 50 MB file. Transcoding is 20–40s of CPU for a 15-minute demo and must not hold a gunicorn worker, so it runs in a daemon thread, serialized behind a one-slot semaphore per process so a burst of uploads queues instead of forking N ffmpeg processes on a 512 MB box.

4. **The queue table is the durability story; the thread is only an optimization.** `Demo.processing_state` (`queued → processing → ready | failed`) is the real record. A deploy or crash mid-transcode leaves a row stuck in `processing`; `manage.py process_demos` reclaims anything older than `DEMO_STALE_PROCESSING_MINUTES` back to `queued` and drains the queue. That command is the backstop, is wired to a button in the admin queue, and can be put on a cheap every-15-minutes Render cron if the producer wants belt and braces — but nothing depends on a per-minute cron container. Claiming is a conditional `UPDATE ... WHERE processing_state='queued'` checked by row count, so the thread and the command can never both process the same demo.

5. **A demo reaches the moderation queue only once it is `ready`.** Moderators approve by listening, and the thing they listen to is the transcoded stream copy. Surfacing a still-transcoding demo would mean either a dead player or serving the untouched original, which still carries its ID3 tags. Failed demos get their own section in the queue with the ffmpeg error, so a broken upload is visible rather than silently absent.

6. **Originals are stored but never served.** §3.2 says store the original *and* a streaming copy. Only the stream copy is transcoded with `-map_metadata -1`, so the original still carries whatever ID3 tags, cover art, and authoring software the uploader's machine wrote into it — which can include a real name. Originals go under a `private/` key prefix, the public page and the moderation player both point at the `public/` stream copy, and no template ever renders an original path. Because R2's public custom domain serves the whole bucket, **A.4 gains a checklist line**: add a Cloudflare rule blocking `/private/*` on `media.noagendatalentsearch.com`. Until R2 exists this is moot — dev stores under `MEDIA_ROOT` and Django only serves media at all when `DEBUG` is on.

7. **Storage switches on credentials, exactly like email did in Phase 1.** `RESEND_API_KEY` set → SMTP backend, unset → console backend, no redeploy. Same shape here: R2 variables present → `django-storages` S3 backend pointed at the R2 endpoint with `querystring_auth=False` and the public custom domain; absent → `FileSystemStorage` under `MEDIA_ROOT`. A.4 is still unchecked, so the site runs on local disk today and becomes an R2 site the moment the bucket exists. Every path in the codebase goes through `default_storage`, so nothing else has to know which is in play.

8. **Upload rate limiting is pulled forward from Phase 5.** Rate limits are a Phase 5 item, but this phase adds the first authenticated endpoint that accepts 50 MB and spawns an ffmpeg process. A per-account cap of `MAX_DEMO_UPLOADS_PER_DAY` (5), counted off the `Demo` table in the same style as `accounts/ratelimit.py`, closes the obvious way to pin the transcode worker. The rest of §8's limits stay in Phase 5.

9. **Moderation actions write audit-log entries now.** `AdminAuditLog` already exists from Phase 1 and the queue is the first screen that takes consequential, irreversible-feeling actions on other people's submissions. Writing entries here costs a helper function and means the Phase 5 audit-log viewer has real data to show. §4.1's settings-change entries are still Phase 4/5.

10. **`guest_host` is derived, not stored.** §3.2 lists it among the admin-set candidate flags, but §5's data model has no column for it and Phase 4 introduces `Appearance` rows that answer the same question exactly. Storing a hand-set boolean alongside the appearance table guarantees the two disagree eventually. `is_featured` *is* stored, because nothing derives it.

## The upload pipeline

`POST /audition/demo/` — login required, one active candidate profile required.

**Validate, in order, rejecting with a plain-language message at the first failure:**

| Check | Rule | Source |
|---|---|---|
| Rate limit | ≤ 5 uploads per account per 24h | decision 8 |
| Declared size | `≤ demo_max_file_mb` (runtime setting, default 50) | §3.2, §4.1 |
| Extension | `.mp3` | §3.2 — a courtesy check only, never the real one |
| **Container** | `ffprobe` reports an `mp3` format | §8 "magic bytes, ffprobe, never trusted by extension" |
| **Codec** | exactly one audio stream, `codec_name == "mp3"` | as above |
| Duration | `1 ≤ duration ≤ demo_max_duration_sec` (default 900) | §3.2, §4.1 |

A `.wav` renamed to `.mp3` fails the container check; an mp4 with an mp3 track fails it too. Embedded cover art is tolerated on input (it is a normal `attached_pic` stream) and dropped on output.

**Store and queue.** The original is written to `private/demos/<uuid>/original.mp3`, a `Demo` row is created with `status=pending, processing_state=queued`, any previous demo for that candidate is moved to `archived`, and the response redirects back to `/audition` with the row visible. Ratings on the archived demo stay attached to it — `Rating.rateable_id` points at the demo, so a new demo is a genuinely new rating slate with no migration, per §3.2.

**Transcode.**

```
ffmpeg -nostdin -y -i <original> -vn -map 0:a:0 -map_metadata -1 \
       -codec:a libmp3lame -b:a 128k -ar 44100 <stream>
```

`-map_metadata -1` is the ID3 strip §3.2 asks for; `-vn` drops embedded artwork, which is both bandwidth and a place to hide a payload. Output lands at `public/demos/<uuid>/stream.mp3` and the row goes `ready`.

**Photos** are handled synchronously — Pillow decodes, `exif_transpose` applies the orientation tag, then the image is re-encoded as JPEG within 600×600. Re-encoding is what strips EXIF (including GPS), so it happens even for an already-small image. Non-image data, a pixel count over the bomb threshold, or a format outside jpg/png/webp is rejected; 5 MB cap per §3.2.

## Pages

- **`/candidates`** — approved candidates only, sortable by newest or name. "Top demos" is listed in §6 as a third sort but needs the Phase 4 scoring columns to mean anything, so it lands with Phase 4 rather than shipping as a stub that sorts by nothing.
- **`/candidates/:slug`** — approved stage name, bio, photo, and an `<audio controls preload="none">` on the live demo. `preload="none"` matters: this page will be linked from the show, and preloading would pull a few MB per visitor off R2 before anyone presses play. Appearance history is a labelled placeholder for Phase 4.
- **`/audition`** — the candidate's own workspace: profile form, current demo with a player, submission status, and whichever of "pending review", "live", "rejected, here's why", "edits awaiting review", or "withdrawn" applies. A candidate can always hear their own demo, live or not. Gated on the `auditions_open` runtime setting.
- **`/`** — gains the "Audition" CTA §6 calls for.

Withdrawing is self-service and reversible: `withdrawn` hides the profile, re-opening returns it to `pending` for re-approval rather than straight back to `live`.

## Moderation queue

One screen inside Django admin at **Candidates → Moderation queue**, sectioned into new candidates, profile edits awaiting review, demos awaiting review (each with an inline player), and demos that failed to transcode. Approve and reject are POST-only forms; reject takes a canned reason from a fixed list plus an optional note, and both outcomes email the candidate. Every action writes an `AdminAuditLog` row. A "Process queued demos now" button runs the backstop command in-process.

Canned reasons: audio quality, not an audition demo, breaks the house rules, identity not verified, duplicate submission, other. The emailed text is a full sentence written for a fellow producer having a bad day, not a status code — principle #3.

## Testing

- **Upload validation** (called out in §9 as one of the four places silent bugs hurt most): oversize, over-duration, zero-duration, `.wav` renamed to `.mp3`, mp4-with-mp3-track, text file with an `.mp3` extension, and a valid file at the boundary. Real files generated by ffmpeg in `setUpClass`, so the assertions are about actual container inspection rather than a mocked probe.
- **Transcode**: output is a real mp3, is 128 kbps, keeps the source duration, and carries no ID3 tags or cover art from the input.
- **Queue mechanics**: claiming is atomic (a second worker on a claimed row is a no-op), stale `processing` rows are reclaimed, a failed transcode records the error and does not surface publicly.
- **Pre-moderation**: an unapproved bio never appears in any public response — asserted against the rendered HTML of both public pages, not against the model. A live candidate's edit does not change what the public page shows until approval.
- **Access control**: pending, rejected, withdrawn, and banned candidates 404 on the public page and are absent from the list; a candidate can see their own; moderator-only endpoints reject a producer account.
- **Ownership**: one profile per account; a user cannot upload a demo onto someone else's profile.
- **Demo replacement** archives the old row and leaves its ratings attached to it.
- **Storage indirection**: tests run against a temp-directory `FileSystemStorage`, and one test asserts the R2 settings block produces the expected S3 backend configuration when the environment variables are present.

## Out of scope for Phase 3

Demo and appearance ratings, scoring, the leaderboard and Rising Demos, appearance tagging (Phase 4); reports, Turnstile, the remaining §8 rate limits, the admin digest email, and vote-velocity analytics (Phase 5); and the episode-artwork R2 caching noted as a follow-up in the Phase 2 design — that one is worth doing but belongs with a broader media pass, not bolted onto the audition pipeline.
