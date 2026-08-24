# No Agenda Talent Search — visual rebuild prompt

Paste this entire document into a frontend / design agent working against the live site (noagendatalentsearch.com) or a fresh app. Recreate the look and feel of the approved mock as closely as possible. Do not invent a second art direction.

---

## Role

You are an expert frontend engineer, UI/UX designer, visual design specialist, and typography expert. Integrate this design system into the existing codebase in a way that is visually consistent, maintainable, and idiomatic to the tech stack.

Before writing code: identify the stack, existing tokens, component architecture, and constraints. Centralize tokens. Prefer reuse over one-off styles. Match existing folder / naming patterns.

This is a restyle of an existing product, not a new product concept. Keep current routes, copy intent, and producer language. Change the chrome, type, lighting, and talent-card treatment.

---

## Product (do not redesign the job)

**No Agenda Talent Search** is the producer-driven audition for the show’s next guest-host.

- Audience calls themselves **producers** (not users, not fans, not contestants-as-customers).
- They send demo tapes, listen, and rate. Ratings **inform** who sits in the chair. They do **not** fill it.
- Comedy-adjacent: light conspiracy, political commentary, media deconstruction.
- Libertarian-leaning. No in-your-face rulebook energy.
- Tone: late-night AM radio, troll room, crazy-fun-uncle — not Silicon Valley, not network talent-show IP.

Nod to *America’s Got Talent* / *Star Search* (marquee type, portrait-forward talent board, a stage) **without copying logos, colors, set design, judges desk, golden buzzer, or catchphrases.**

---

## Visual metaphor

A **dark venue with the lights up enough to read**, not a nightclub and not a Linear-style SaaS dashboard.

The page is a dressing-room corkboard in front of a stage:

- Magenta and purple-blue **theatrical gels** in the atmosphere (two colors only; multiple sources / intensities of those two is fine).
- A **warm tungsten follow-spot** only on the hero photograph of two vintage mics. That warm light is part of the photo, not a third UI gel, and it is **not** the ratings-star color.
- Talent photos are **Polaroids taped to the wall**, slightly crooked, with handwritten names on the cream border.
- Section labels are **rubber stamps**, not all-caps tracking kickers everywhere.
- A condensed **bumper-sticker ticker** under the header, like a radio station ID.

The room should feel slightly unhinged in a fun-uncle way. Never costume, never emoji, never carnival, never “AI purple glow SaaS.”

---

## Color tokens (use these exact values)

```
--bg:            #1c191f    /* lifted near-black, readable at normal brightness */
--bg-deep:       #141217
--surface:       #27232c
--surface-2:     #302c36
--fg:            #f7f3eb    /* cream, not pure white */
--muted:         #b8b0a6
--faint:         #908880
--line:          #433e48
--accent:        #f7f3eb    /* cream follow-spot for primary buttons */
--accent-fg:     #1a171c    /* ink on cream buttons */
--gel-magenta:   #d4527e
--gel-blue:      #5a4ecf    /* purple / theatrical blue */
--star:          #daa520    /* goldenrod — RATINGS ONLY */
--star-hot:      #e8b923
--ok:            #7bbf95
--bad:           #e78585
```

### Color rules (non-negotiable)

1. **Goldenrod / yellow / orange is reserved for star ratings.** Do not use it on buttons, links, gels, headings, borders, or decoration. The hero follow-spot may stay warm in the *photograph*; do not echo that warmth as a UI token.
2. **Primary buttons are cream (`--accent`) on dark**, with dark text (`--accent-fg`). Not magenta, not blue, not gold.
3. Magenta and blue are **stage gels and sparse stamps**, not brand fills. Never paint large surfaces with them. Never use purple as a primary button / link / heading color.
4. No pure `#000000` page background. No pure `#FFFFFF` body text.
5. Page background is **two gel colors only** (magenta + purple-blue), multiple radial sources allowed. Do not add a third ambient hue (no amber, no teal, no extra cool gray wash).
6. Borders are quiet: 1px cream at ~10–20% opacity, not prominent strokes.

### Stage wash (exact recipe)

Apply on the app root:

```css
background:
  radial-gradient(ellipse 95% 52% at 50% -6%, rgba(212, 82, 126, 0.34), transparent 58%),
  radial-gradient(ellipse 38% 42% at 8% 4%,  rgba(212, 82, 126, 0.16), transparent 50%),
  radial-gradient(ellipse 50% 52% at 94% 0%, rgba(90, 78, 207, 0.34), transparent 56%),
  radial-gradient(ellipse 32% 38% at 80% 22%, rgba(90, 78, 207, 0.12), transparent 48%),
  var(--bg);
```

Overlay a faint fractal-noise film at **3.5–4% opacity**. Do not go heavier.

---

## Typography

Load from Google Fonts:

- **Display:** `Big Shoulders Display` weights 500/600/700. Condensed marquee. Uppercase. Tight line-height (~0.9). Tracking ~0.02em. Page titles, section titles, talent names in headers, ticker.
- **Body / UI:** `Figtree` 400/500/600/700 + italic 400. All paragraphs, nav, buttons.
- **Marks / stamps / polaroid captions:** `Shantell Sans` 500/600 + italic 500. Handwritten-but-legible. Used sparingly.

Do not use Inter, Roboto, Space Grotesk, or a third display face. Do not use Comic / “fun” display fonts. Shantell Sans is the only informal face, and only on stamps, polaroid names, and one footer line (“In the morning.”).

Type scale (display):

- Hero: `clamp(3.2rem, 12vw, 7.2rem)` stacked **TALENT / SEARCH**
- Page H1: ~5xl mobile / 7xl desktop
- Section H2: ~4xl / 5xl
- Compact card names live in the polaroid caption, not as a second huge headline under the photo

Body: 16px, relaxed leading. Muted color for supporting copy.

---

## Motion

- Duration 150–200ms. Easing `cubic-bezier(0.22, 1, 0.36, 1)` (expo-out).
- Hover travel ≤ 8px. Polaroids straighten and lift 4px.
- No springs, no bounce, no elastic overshoot.
- Ticker: CSS `translateX` loop, ~42s, linear, pause conceptually under `prefers-reduced-motion` (disable the animation; leave one static row).
- Respect `prefers-reduced-motion`: kill marquee, kill polaroid tilt.

---

## Components

### Header

Sticky, `bg` at ~92% with backdrop blur, hairline border.

Left: existing No Agenda eagle/mic logo + stacked “NO AGENDA” kicker + “TALENT SEARCH” display.

Right: text links (Candidates, Episodes, Favorites, About) in muted Figtree. Active = cream. Primary **Audition** is a cream rounded-md button.

Under the header bar, a full-width **marquee / bumper ticker** (not a second nav). Condensed uppercase display at ~0.78rem, tracking 0.18em, muted cream, magenta middle-dot separators.

Ticker phrases (this exact list — do **not** add “Not a vote”):

- In the morning
- Value for value
- Calling all ships at sea, boots on the ground, feet in the air, subs in the water, and all the dames and knights out there...
- I got Ants!
- No ads · no masters
- Time · talent · treasure
- Troll room is listening
- Media deconstruction
- Jingles welcome

Duplicate the list so the loop is seamless.

### Rubber stamp

Inline label, Shantell Sans, ~0.82rem, uppercase, 2px solid border, 3px radius, padding ~0.18em 0.55em.

- Default stamp: magenta border + magenta text, rotate **-2.5deg**
- Alternate `.stamp-blue`: blue border, lightened blue text, rotate **+2deg**

Use stamps for section labels (`In the morning`, `Rising demos`, `Currently leading`, `What this is not`, `Open audition`, `The board`). Do not stamp every sentence.

### Polaroid talent card

Cream (`--accent`) frame. Padding ~7px, extra ~2.1rem at the bottom for the handwritten name.

Photo is square on the board, `object-cover` with `object-position: center 20%` so faces aren’t cropped.

Magenta gel + blue gel color-wash overlay on the photo via `mix-blend-mode: color` (diagonal: magenta 38% → transparent → blue 38%). This unifies real headshots with the stage; do not duotone them to a single color.

A small translucent **magenta tape** rectangle sits on the top edge, slightly rotated.

Each card gets a **stable per-slug tilt** between about -2.4deg and +2.4deg (hash the slug; do not randomize on every render). Hover / focus: rotate back to 0deg and translateY(-4px).

Name is written on the cream border in Shantell Sans (not a second display headline under the card). Snippet + goldenrod stars sit **under** the polaroid on the dark stage, not on the cream.

If the candidate is sample/placeholder, a tiny “Sample” pill in the photo corner.

**Grid:** 4–5 compact polaroids per row on desktop (not 2–3 giant headshots). 2 per row on small screens. Cards should feel like you’re looking at a wall of snapshots, not sitting in someone’s lap.

### Featured “currently leading” card (home)

This is **the highest-rated demo among candidates who have not guest-hosted yet** — the #1 Rising Demo. It is **not** “the latest tape” unless nobody has ratings yet (fallback: most recently reviewed).

It is **not** a new product feature; it is a visual callout of existing ranking data. Label it **Currently leading**. Supporting line: ratings are not a vote; this is who’s landing with producers right now.

**Layout (critical):** do **not** stack a tall 4:5 portrait above a block of copy — that dwarfs the adjacent “Not a vote” note and shoves the page down.

- Photo aspect **6:5** (shorter than tall).
- Max width ~16rem on desktop.
- Copy (stamp, one short paragraph, stars, “Listen to the tape →”) sits **beside** the polaroid on `sm+`, aligned to the bottom of the frame.
- The home row is two columns, `items-start`: leading polaroid cluster on the left, taped note on the right.
- Polaroid width is modest; the row should be roughly as tall as the “Not a vote” note, not 1.5–2× taller.

### Taped note (“Not a vote”)

Surface-2 panel, **dashed** cream-at-22% border, ~28px radius, rotated **+1.4deg**. Stamp “What this is not”, display headline **Not a vote**, body explaining that Adam Curry / the show make the call. Link: **The concept →** (do not call this “House rules”, “Rules”, “Terms”, or “Guidelines”).

### Stars

Goldenrod `#daa520` / hover `#e8b923`. Five stars. Numeric average + count in muted Figtree. Interactive stars on the candidate demo page. Empty stars are cream at low opacity, never gray-blue. No other gold in the UI.

### Buttons

- Primary: cream fill, dark text, 8px radius (`rounded-md`), min-height 48px, no glow, no gradient.
- Secondary: transparent with 1px cream at ~22% opacity.
- Press scale 0.96 if you animate press. No bounce.

### Footer

Hairline top border. Left: “Producers advise. The show decides. Everything is reviewed before it goes public.” Right: Shantell Sans magenta **Value for value**

---

## Page layouts

### Home

1. **Hero** — full-bleed rounded-[28px] stage photograph of two vintage mics on a dark empty stage. Warm follow-spot on the mics (keep the photo’s tungsten; do not recolor it gold or magenta). Overlay is **left-to-right**, not a heavy center vignette, so type on the left stays readable and the mics on the right stay visible:

   - `bg-gradient-to-r from-bg from-5% via-bg/80 via-40% to-transparent to-80%`
   - plus a light bottom fade `from-bg/70 to-transparent to-45%`

   Magenta stamp “In the morning”. Giant stacked TALENT / SEARCH. One paragraph. Two CTAs: **Audition for the Show** (cream) and **Rate guest appearances** (ghost). Fine print: everything is reviewed; ratings inform the chair — they don’t fill it.

2. **Leading demo + Not a vote** — layout described above.

3. **Rising demos** — stamp + “The house is listening”. Four compact polaroids. Link to Favorites.

4. **Latest episodes** — stamp-blue “From the feed”. Rows with show-art thumbs (keep the real chaotic No Agenda episode art; do not restyle it into Polaroids). Guest-host chip when present.

### Candidates

Stamp “Open audition”. Title Candidates. Short producer-voice intro. **5-column polaroid grid** on large screens, 2 on small. Real candidates first; placeholders marked Sample.

### Candidate detail

Back link. Polaroid (~220px) + stamp (Reviewed candidate / Sample card) + display name + stars. Bio. Demo tape player. “Your rating” on a surface card with interactive goldenrod stars. Copy: rate the performance, not the person; one rating per producer.

### Favorites / leaderboard

Stamp “The board”. Title Community favorites. Empty dashed well for show appearances until guest hosts exist. Rising demos as a ranked list: number, mini-polaroid thumb, name, snippet, stars. Copy: standings inform the show; they don’t make the decision.

### About

Stamp “In the morning”. Title About the search. Body from the live site. A section titled **The compact** (voluntary producer language — not rules). List: send a tape, producers listen, show decides, everything reviewed, ratings aren’t a vote, value for value.

### Audition

Keep the existing form. Restyle to this chrome (stamps, surfaces, cream submit). Do not invent new fields.

---

## Copy / naming

Preferred words: producers, demo tape, guest-host, the chair, in the morning, value for value, producers advise, the show decides, the compact, currently leading, rising demos.

Avoid: users, contestants (as UI chrome), house rules, terms, vote-to-win, golden buzzer, America’s Got Talent, Star Search (those two may appear only in an internal design note, never on the site).

“Not a vote” is a **page module**, not a ticker phrase.

---

## Hero image spec (if regenerating)

Photoreal empty dark theater / club stage. Two vintage broadcast mics on stands, close, right-of-center. Warm tungsten follow-spot on the mics only. Magenta gel in the left/overhead air, purple-blue gel from stage right. Visible enough to read at normal monitor brightness — not crushed blacks. No people, no logo, no text, no buzzer, no judges desk. Landscape, roughly 16:9, suitable as a CSS background with left-side type overlay.

Existing asset filename in the mock: `hero-stage.jpg`.

---

## Accessibility

- Cream `#f7f3eb` on `#1c191f` is the text pairing.
- Muted `#b8b0a6` must stay ≥ 4.5:1 on the lifted bg. Do not darken muted back to the old gray.
- Do not rely on gel color or gold alone for meaning (icons + labels + position).
- Focus rings: 2px cream at ~70%, 3px offset.
- Ticker is `aria-hidden`; real nav is the header links.
- Polaroid tilt disabled under reduced motion.

---

## Anti-patterns (reject these if a model starts drifting)

1. Flat single-color background with no gels / no noise.
2. Three ambient hues (muddy). Amber as a UI gel.
3. Pure black or pure white.
4. Gold anywhere except stars.
5. Magenta or blue filled buttons, gradients on buttons, glow blobs on CTAs.
6. Giant 2-column headshots on the candidates index.
7. Uniform even bento of same-size cards with no tilt / no polaroid.
8. Inter / Space Grotesk / “startup landing” type.
9. Bouncy springs, >8px hover travel, emoji, sticker packs, confetti.
10. “House rules.” Ticker containing “Not a vote.”
11. Copying AGT red-gold-blue, golden buzzer, or Star Search chrome.
12. Linear-app precision (hairline everything, no analog mess). Keep the corkboard.
13. Making the featured polaroid tall (4:5 or 3:4 stacked above copy).
14. Stock catalog smiles / beauty-lighting portraits. Candid, mid-laugh, side-eye, “can you believe this clip.”

---

## Implementation priority

1. Tokens + fonts + stage wash + header/ticker/footer.
2. Hero with left-to-right overlay on the stage photo.
3. Polaroid component + 5-up candidates grid.
4. Home leading-demo row (short 6:5 polaroid beside copy) + taped “Not a vote.”
5. Stars remaining goldenrod.
6. Stamps replacing generic kickers.
7. About “The compact.”
8. Only then: hover polish, reduced-motion, leftover pages.

Ship the chrome. Do not rebuild the product, auth, or CMS in this pass unless the host codebase requires it to render the pages.
