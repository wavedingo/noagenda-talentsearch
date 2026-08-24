# Website Refresh — Design

**Status:** Approved — all decisions resolved 2026-08-24
**Source:** `docs/design/2026-08-24-website-refresh/` (mock export: DESIGN-PROMPT.md, five screenshots, Tailwind reference stylesheet, hero photo)
**Spec:** `specs/noagendatalentsearch-spec.md` §7 (stack), §10 (tone), B.5 (lists, empty states, copy)
**Scope:** Whole-site visual refresh — tokens, fonts, stage wash, header + ticker, footer, hero, polaroid talent cards, stamps. Home gains a hero and two feature cards. No new product features, no schema changes, no auth or moderation changes.

## Decisions

1. **No Tailwind.** The reference stylesheet is Tailwind v4 (`@import "tailwindcss"`, `@theme`), but CLAUDE.md and spec §7 are explicit: server-rendered, no frontend framework, one hand-written stylesheet, dependencies added sparingly. The cost of not adopting it is low — the reference's entire `@layer components` block (stamp, polaroid, photo-gel, taped-note, marquee, surface-card) is already plain CSS and ports near-verbatim. Only the layout utilities written inline in the prompt's prose need translating, roughly 400 hand-written lines on top of the existing 438. Adding a Node build step to the deploy for that trade is a bad deal.

2. **The `@theme` block becomes the existing `:root` block, keeping current variable names.** `--color-bg` → `--bg`, `--color-fg` → `--ink`, `--color-muted` → `--ink-soft`, `--color-line` → `--line`. Renaming in the other direction would touch all 438 existing lines for no gain. New tokens (`--bg-deep`, `--surface-2`, `--faint`, `--accent-fg`, `--gel-magenta`, `--gel-blue`, `--star`, `--star-hot`, the radius and shadow scales) are added alongside. Every existing rule keeps working through the token swap alone — that is the whole point of landing tokens as their own commit.

3. **The site becomes dark-only. The light theme is deleted.** *(A real deletion the mock never mentions.)* Today `:root` is a light palette (`--bg: #faf9f7`) with a `prefers-color-scheme: dark` override. The refresh has no light variant — every screenshot is dark and the stage-wash metaphor (theatrical gels over near-black) does not survive inversion. Consequences: the `<picture>` logo swap in base.html always resolves to `logo-light.svg`, and the two `apple-touch-icon` media queries collapse to the light-on-dark icon. A producer whose OS is in light mode gets a dark site. Given the subject matter — a stage with the lights down — that reads as intent, not as a bug. **Approved: dark-only. The light palette is removed, not kept behind a media query.**

4. **Header keeps `Log in` / `Account`, restyled.** The mock's four-link nav plus a cream `Audition` button drops both. On a magic-link-only site that leaves an anonymous producer no way to sign in from any page. They sit as muted Figtree text links to the left of the Audition button, matching the other nav items. `Audition` continues to respect the `auditions_open` runtime setting and the authenticated check it has today — when it is hidden the nav simply reflows.

5. **The ticker is a static template partial with no database access.** The phrases are hardcoded, so this needs no context processor and no query — it renders on every page including `/django-admin/` at zero cost. `aria-hidden="true"`; the real nav is the header links. The list is duplicated in markup so the 42s `translateX(-50%)` loop is seamless. Under `prefers-reduced-motion` the animation is disabled and one static row remains.

6. **Ticker phrases** — the prompt's list minus "Calling all ships at sea…", which at ~120 characters would occupy roughly a third of the loop on its own:
   In the morning · Value for value · I got Ants! · No ads · no masters · Time · talent · treasure · Troll room is listening · Media deconstruction · Jingles welcome.
   "Not a vote" is deliberately absent — it is a page module, not a ticker phrase.

7. **About keeps all of its current copy.** The mock's About is a visual sketch, not an editorial decision, and it silently drops three load-bearing things: the "A good demo tape" checklist (the only place on the site that tells someone what to record), `hello@noagendatalentsearch.com` (the only contact and takedown address), and the `vote_eligibility_hours` line. "House Rules" is renamed **The compact** per the prompt's naming rules — the prompt is right that "rules" is the wrong register for a voluntary show — but keeps its full paragraphs. The one-line compression in the mock drops exactly the reasoning that does the work for a grieving audience putting themselves forward in public. The `id="house-rules"` anchor is only referenced from within about.html; it becomes `id="the-compact"` with both links updated.

8. **No `SAMPLE` pill.** The mock's sample cards are filler to show a crowded board — the README says so outright. There is no `is_sample` field on `Candidate`, and adding one means a model field, a migration, and admin surface to support a state that only ever existed in a mock. The real board has real candidates and will fill in on its own.

9. **`is_featured` survives as a magenta stamp.** The field is real, has admin filters, and renders a `Featured` badge in `_candidate_card.html` and `candidates/detail.html` today. The mock has no equivalent, so it would silently stop working. It becomes a `.stamp` reading **Featured**, placed with the stars *under* the polaroid — not on the cream border, which is reserved for the handwritten name.

10. **"Currently leading" is always the top Rising Demo, independent of the favorites branch.** Per the prompt: the highest-rated demo among candidates who have *not* guest-hosted yet. That makes it complementary to the grid below rather than redundant with it, and it degrades correctly in both states — today the grid is Rising Demos and the callout is its leader; once guest hosts exist the grid becomes Community favorites (people who have been on the show) and the callout still shows who is coming up behind them. `core.views.home` gains one key, `leading = rising_demos()[:1]`, computed independently of the existing `favorites`/`rising` either-or at core/views.py:19-21. When there are no rising demos at all the module is omitted and the "Not a vote" note takes the full row width.

11. **"Discover Talent" moves onto the Currently leading card.** It is the third button on the home page today and appears nowhere in the mock. That card is already about candidates and ends with "Listen to the tape →", so it gains a secondary ghost button underneath — one specific action, one general one — and the hero stays at the two CTAs the prompt calls for.

12. **Fonts are self-hosted, not loaded from Google.** Three families at the prompt's full weight range is twelve faces from a third-party origin on every page load. Trimmed to what is actually used — Big Shoulders Display 600/700, Figtree 400/600 + italic 400, Shantell Sans 600 — that is six woff2 files, roughly 150–200KB, subset to Latin and served from `static/fonts/`. There is no CSP on the site today so the Google Fonts route would work, but this audience calls itself "no ads, no masters" and would reasonably notice the call home. Self-hosting also removes a render-blocking third-party request on a mobile-first site.

    `CompressedManifestStaticFilesStorage` (config/settings.py:130-136) rewrites relative `url()` references in CSS at `collectstatic` time, so the faces get content-hashed names, brotli compression and immutable cache headers for free. The "already cached from another site" argument for Google Fonts has not held since browsers partitioned the HTTP cache by origin in 2020 — a first-time visitor pays for the download either way, and via Google also pays a second DNS lookup, TLS handshake and render-blocking round trip.

    **Reverting is a single commit at any time, including post-launch:** the `font-family` names are identical either way, so it is delete the `@font-face` block, add one `<link>` to base.html, delete `static/fonts/`. No other rule changes.

13. **The gel colours are not accessible as text and get separate text tokens.** Measured against `--bg: #1c191f`:

    | Token | On `--bg` | On `--surface-2` |
    |---|---|---|
    | `--ink` `#f7f3eb` | 15.70 | 12.33 |
    | `--ink-soft` `#b8b0a6` | 8.11 | 6.37 |
    | `--faint` `#908880` | 4.98 | **3.91 ✗** |
    | `--gel-magenta` `#d4527e` | **4.39 ✗** | **3.45 ✗** |
    | `--gel-blue` `#5a4ecf` | **2.84 ✗** | **2.23 ✗** |
    | `--star` `#daa520` | 7.77 | 6.10 |

    The prompt's claim that muted stays ≥4.5:1 holds. But `.stamp` sets 0.82rem magenta text — not large text — at 4.39:1, and stamps carry real section names ("Rising demos", "Currently leading"). So: `--gel-magenta-text: #dd7a99` (6.06 / 4.75) and `--gel-blue-text: #a198dc` (6.65 / 5.22) for any text use; `#d4527e` and `#5a4ecf` stay exactly as specified for borders, tape, gradients and the photo gel wash, where text contrast does not apply. This keeps the mock's look — the shift is small — while making the stamps readable. `--faint` is restricted to `--bg` and must never carry body text inside a surface card.

14. **The hero photograph ships as-is, against its own spec.** `hero.jpg` is magenta on the left and **amber-gold on the right**, with no purple-blue gel anywhere. The prompt's colour rule 5 says two gels only and names amber as forbidden; anti-pattern 4 is "gold anywhere except stars". It is a photograph rather than a UI token so it is defensible, but the amber is a large saturated field rather than a "follow-spot on the mics only", and on the home page it sits directly above goldenrod rating stars. **Approved as-is — noted here so the conflict is on record if the amber ever reads wrong next to the goldenrod stars.** Separately, and regardless: `hero.webp` is 370KB against the JPEG's 390KB at identical 1792×1008, so the WebP encode is buying nothing. Re-encode properly and add a ~900px variant for phones behind `<picture>`. `docs/design/.../assets/hero.jpg` is byte-identical to `static/img/hero.jpg` and gets deleted.

15. **Episode artwork is not restyled.** Per the prompt: the real chaotic No Agenda episode art stays as-is in its square thumb. It does not become a polaroid.

16. **`Episode.enclosure_url` remains unrendered.** Unchanged from today, restated because this pass rewrites the episode card markup and the OP3 prefix would register a false download. Cards link to `link_url`. Likewise the feed's `role="host"` people stay unrendered.

## Token map

Reference `@theme` → `site.css :root`. Existing names on the left of the arrow are unchanged from today.

```
--bg          #1c191f    (was #faf9f7 light / #171614 dark)
--bg-deep     #141217    new — ticker bar backing
--surface     #27232c
--surface-2   #302c36    new — taped note, rating panel
--ink         #f7f3eb
--ink-soft    #b8b0a6
--faint       #908880    new — on --bg only, see decision 13
--line        #433e48
--accent      #f7f3eb    ⚠ changes meaning: was the link/CTA colour,
                          becomes the cream primary-button fill
--accent-fg   #1a171c    new — ink on cream buttons
--gel-magenta #d4527e    borders, tape, wash
--gel-blue    #5a4ecf    borders, wash
--gel-magenta-text #dd7a99   new — stamp text (decision 13)
--gel-blue-text    #a198dc   new — stamp-blue text (decision 13)
--star        #daa520    ratings only
--star-hot    #e8b923    ratings hover only
--ok          #7bbf95    (unchanged from current dark palette)
--bad         #e78585    (unchanged from current dark palette)
--radius-xs/sm/md/lg/xl  4 / 8 / 12 / 18 / 28px   (replaces single --radius: 10px)
```

`--accent` changing meaning is the one trap in the token commit: today it is the orange link colour, tomorrow it is cream button fill. Links become `--ink` with an underline rather than a coloured word, per the prompt's rule that magenta and blue are never link colours.

## Components

`.stamp` / `.stamp-blue`, `.polaroid` (+ `.polaroid-mini`, `.polaroid-caption`), `.photo-gel`, `.taped-note`, `.surface-card`, `.marquee` / `.marquee-track` / `.marquee-item`, `.stage-root` wash + noise film, `.display` / `.kicker` / `.mark` type helpers. All lifted from the reference stylesheet with the token renames applied.

**Polaroid tilt is a stable per-slug hash**, not randomised per render, so a card does not jump between page loads. A small template filter hashes `candidate.slug` to a value in ±2.4deg and sets `--tilt` inline. Hover and focus straighten to 0deg and lift 4px; both are disabled under `prefers-reduced-motion`.

## Pages

- **Home** — hero (left-to-right overlay, type left, mics right) → Currently leading + Not a vote row → Rising demos (or Community favorites) polaroid grid → Latest episodes → footer.
- **Candidates** — stamp, display title, existing sort bar restyled as pills, 5-up polaroid grid on desktop / 2-up on phones, existing pagination restyled.
- **Candidate detail** — polaroid ~220px, stamp, display name, stars, bio, player, rating widget on a `--surface-2` card.
- **Favorites** — already structurally identical to the mock; stamps and type only.
- **About** — stamps and type only, plus the House Rules → The compact rename.
- **Audition, account, auth, moderation, error pages** — chrome only. No form changes, no new fields.

## Out of scope

Schema changes, the `SAMPLE` pill, auth flow changes, moderation UI, any new sort or filter, JavaScript beyond none (the marquee is CSS-only, the rating widget stays a five-button POST).

## Decided during implementation

17. **Only the top three board rows carry an ordinal.** The mock numbers every
    row 01-07 on Favorites and 01-04 on the home board. Spec 1.3 ("celebrate the
    top; never publicly rank the bottom") is satisfied by numbering the podium,
    but Phase 4 decision 11 went further -- "no `#1` / `#2`, ordinals invite a
    race the copy says this is not" -- and that stricter rule is **superseded
    here**. Rows past third render a blank rank cell so the columns still line
    up. See `docs/superpowers/specs/2026-08-22-phase4-ratings-design.md`.

18. **The footer mark is a link to noagendadonations.com**, not a slogan. The
    prompt says "Value for value" and the screenshots say "In the morning."; the
    resolution is the prompt's words pointing at the show's donation page, in a
    new tab with `rel="noopener noreferrer"` and a visually-hidden note that it
    opens a new tab.

19. **The Currently leading card has an empty state.** Discover Talent lives on
    that card, and the card only renders when a rising demo exists -- so on a
    quiet board the button vanished from the home page entirely. The slot now
    renders a second card either way, keeping the row at two.

20. **The gel wash comes off when there is no photograph.** Washing an empty
    frame renders a magenta-to-blue gradient swatch that reads as a broken
    image. No photo means an empty cream frame and a pencilled question mark.

21. **The hero re-encode.** 1792px WebP at q76 is 64KB (from 370KB) and the
    900px phone variant is 22KB. Served via `<picture>` with JPEG fallbacks at
    both widths.

## Commit sequence

1. Tokens + fonts — `:root` swap, self-hosted faces, dark-only. Every page shifts colour; no layout moves.
2. Chrome — stage wash, header + ticker, footer, buttons, links.
3. Polaroid + stamps — card component, candidates grid, favorites list, detail page.
4. Home — hero, Currently leading, Not a vote, section restyle.
5. Remaining pages — about, audition, account, auth, errors.
6. Motion polish, reduced-motion audit, template-syntax regression check.
