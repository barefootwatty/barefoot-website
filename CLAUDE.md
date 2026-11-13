# CLAUDE.md — Barefoot Fishing Safaris website

Read this first in every session on this repo. The owner is GW (Watty), a
fishing guide, not a programmer: explain plainly.

**Whenever GW has to do anything, hand him ONE path, never a menu of options.**
Pick the best route yourself and give:
- every step, numbered, naming exactly what to click or open;
- a clickable link for every web page, and the exact folder path for every
  Mac folder (or a Terminal command that opens it);
- everything he has to copy and paste, each in its own code block, complete,
  with nothing left for him to fill in or edit.
If a step might fail, say what he'll see and what to do then, inside that step.
He should never have to ask for links or steps.

**This repo is PUBLIC.** Nothing private goes in it: no client names, no trip
details, no credentials, no internal pricing notes or commentary on other
operators. That covers files, commit messages and branch names.

## Where the website lives

- **GitHub `barefootwatty/barefoot-website`, branch `main`, is the master.**
- **Vercel serves `main` exactly as it is.** There is no build step on deploy, so
  a push to `main` is live in a minute or two. Never push to `main` without GW's
  go unless the job he gave you says to.
- Every page is plain static HTML. The generated ones are produced by the
  scripts in `pipeline/tools/` and **committed already built**.
- `pipeline/` and `.github/` never reach the live site (see `.vercelignore`).
- GW's Mac has a working copy at `~/Claude/Projects/Barefoot Website Rebuild/`
  (`site/` = this repo, plus `tools/` and `transcripts-master/`). A Drive backup
  sits in "Barefoot Fishing website build 2025 / project-backup". **This repo
  copy of the tools is the one to use and edit.** If the Mac copy differs, the
  repo wins.

## How every page is built

| Pages | Built by | Source | Command / rule |
|---|---|---|---|
| Home, run-off, Dundee/Bynoe, fly fishing, best time, about, gallery, booking terms, privacy, consulting, outdoors, four pillars, Barra Brain, tides cheat sheet, 404 | **Hand-written HTML** from the band system in `styles.css` | the page itself | Edit the page. No one-off treatments: a new layout goes into `styles.css` so other pages can reuse it. |
| Date list + enquiry-form tiles on home, run-off, fly, Dundee/Bynoe (`AVAIL:LIST` / `AVAIL:PICKER` blocks) | `pipeline/tools/build_availability.py` | `assets/availability.json` | `python3 pipeline/tools/build_availability.py .` from the repo root. **Never hand-edit those blocks.** Held/booked rules: `pipeline/README.md`. |
| Articles `media/article-*.html`, their cards on `media.html`, their sitemap rows | `pipeline/tools/build_article.py` (+ `check_places.py`) | `pipeline/articles/src/*.txt`, `placenames.txt`, `manifest.json` | Steps in `pipeline/README.md` (needs the `ROOT/{tools,articles,site}` layout). |
| Radio, podcast and video pages `media/bag-a-barra-*`, `abc-*`, `video-*`, interviews | `pipeline/tools/build_media.py` (uses `clean_transcript.py`) | raw transcripts + `episodes-all.json` in `transcripts-master/` (**Mac and Drive only, not in this repo**) | `python3 tools/build_media.py <site_dir> <episodes-all.json>` |
| Topic pages `topics/*.html` and `topics.html` | `pipeline/tools/build_topics.py` (uses `clean_transcript.py`) | the same transcripts | `python3 tools/build_topics.py <site_dir> <episodes-all.json>` |
| Weekly Bag a Barra: new episode page, `media.html` year list and counts, sitemap row | `pipeline/tools/publish_bagabarra.py` | the Omny podcast feed | **Mac only.** It transcribes on-device with `transcribe.swift` (Apple Speech, free), then commits and pushes `main`. `--dry-run` shows what's new. |
| Canonical + social-preview tags on every page | `pipeline/tools/sitemeta.py` (called by every builder), `add_social_meta.py` for hand pages | | `python3 tools/add_social_meta.py --dry-run` should say 0 pages. |
| `media.html` (the Media Centre) | Hand-written; the article and Bag a Barra scripts insert their own cards and counts | | Edit by hand outside those cards. |
| `sitemap.xml` | Added to by `build_article.py` and `publish_bagabarra.py` | | Add hand pages by hand. |
| Redirects, clean URLs, extra domains (barefootoutdoors, barefootconsulting) | `vercel.json` | | Old-site URLs that must keep working are listed in `pipeline/legacy-paths.txt`. |
| Enquiry form back end + auto-reply | `api/enquiry.js` (Vercel function) | reads `assets/availability.json` live | Needs `RESEND_API_KEY` set in Vercel, never in the repo. |
| Images `assets/img/*-{640,1000,1600}.{avif,jpg}` | `optimize-images.sh` (**Mac only**, uses `sips`) | `assets/raw/` (not committed) | AVIF heights must be even, or Chromium paints them blank. |
| `llms.txt`, `robots.txt` | Hand-written | | |

**The rule that keeps biting:** anything a site-wide script changes on built
pages must also go into the generator (and `sitemeta.py` for head tags), or the
next rebuild silently reverts hundreds of pages.

**Transcripts never go in this repo.** They include radio ad reads that aren't
ours to republish. Only the cleaned segment text appears on the site.
`clean_transcript.py` trims the ads and fixes the transcriber's mishearings.
A fix added there applies to every page on the next rebuild.

## Checks before anything goes live

1. `python3 tools/prelaunch_audit.py` (from the `ROOT/{tools,site}` layout) must
   print PASS.
2. Look at the change at phone width (375px). Most visitors are on phones.
   Headless Chrome clamps windows to 500px, so test 375px inside an
   `<iframe style="width:375px">` wrapper.
3. After a push, the GitHub "Site check" action (`.github/workflows/site-check.yml`)
   checks the live site. It also runs every Monday.

## Standing rules

- Australian English. Prices in AUD.
- Client names and trip details live in the Barefoot Google Calendar only.
  Dates on the site are Available / Held · deposit pending / Booked, nothing else.
- Brand: Barefoot only, never Angling Adventures colours or fonts. Display H1/H2
  Fraunces light, UI Montserrat, body Open Sans, Lora italic for quotes only.
  Copper Sand `#C97B47` and Ironbark Navy `#16314E`. Never Sunset Orange as a
  fill. The full brand reference is held by the Monty skill.
- Copy comes from GW or the live site. Never invent trips, prices, testimonials
  or contact details. Flag new copy for GW to approve before it ships.
- One conversion action per page: "Check dates & enquire". Everything else is a
  text link.
- Every card that links somewhere is clickable across its whole face.

## Design and build rules (moved in from the old Mac notes, 13 Nov 2026)

### Approved deviations (GW signed off: don't "fix" these)
- **Images are AVIF + JPEG fallback** via `optimize-images.sh` (widths
  1600/1000/640), not WebP. Smaller and sharper; the fallback covers old browsers.
- **One line-art fish SVG in each page hero**, beside the H1. Part of the Eleven
  hero GW approved 10 Aug 2026. Hero only: no drawn fish anywhere else.
- **H1/H2 are Fraunces 300–400**, never bold. Montserrat is UI only.
- **No npx / Node skills on GW's Mac.** Deliberate; don't stall a job trying to install them.

### Gotchas
- **AVIF:** `sips` AVIFs with odd pixel heights at 1600w paint BLANK in Chromium.
  Fix the raw source to an even-safe ratio (e.g. `sips -z 2132 3200 raw.jpg`),
  because the optimiser re-runs over all of `assets/raw/` and would undo a fix
  on the output. Eyeball AVIFs in a browser grid before shipping.
- **Kit forms:** the form `action` uses the **numeric form id**
  (Black Book = `https://app.kit.com/forms/9706760/subscriptions`), not the embed
  UID, which silently 404s. The numeric id is inside the embed JS at
  `https://barefoot-outdoors.kit.com/<uid>/index.js`. Fetch with
  `Accept: application/json` and check `status`; never confirm optimistically.

### Eleven design language (locked 10 Aug 2026, every page)
- **Hero:** eyebrow = place + coordinates ("KAKADU NT / -12.66°S, 132.48°E"),
  line-art fish beside the serif H1, quiet tracked sub-line. **No hero button**:
  the sticky section-nav carries the conversion.
- **Sticky section-nav** (`.sectionnav`, body class `has-sectionnav`) on every
  charter page: 3–4 section anchors + Enquire.
- **Buttons:** small uppercase, tracked, pill radius, copper/navy fills, slow
  700ms hover fades, no position jumps.
- **Dark-band rhythm:** vary long pages navy → eucalypt (`.navy.eucalypt`) →
  navy → charcoal (`.navy.charcoalband`). Each variant at most once per page;
  never cold grey.
- **Motion:** scroll-reveal `.rv`/`.in`, staggered ~110ms, off under
  prefers-reduced-motion and without IntersectionObserver. Don't tighten the
  observer threshold (deadlock risk; see the page script comment).
- **Breathing room:** sections pad `clamp(76px,9vw,150px)`.

### Colours, type and contrast
- Tokens: Copper Sand `#C97B47` (CTAs, highlights) · Ironbark Navy `#16314E`
  (headings, nav) · Beach Cream `#F6F1E7` (backgrounds) · Dune Sand `#E5D6C0`
  (cards, dividers) · Charcoal `#211C17` (body) · Slate `#5E6B72` (captions) ·
  Sunset Orange `#DA5A1E` (spark accent only, never a fill) · Eucalypt Sage
  `#6E8169` (carbon-positive accent, sparingly).
- Copper on navy only at large/button sizes (≈3.9:1), never body text.
  Everyday CTAs and small text: navy fill with cream/white text, or charcoal on light.
  Never orange or copper as small text on white.
- Fonts are bundled in `assets/fonts/` (Fraunces, Montserrat and Open Sans are
  variable: one file each, don't add per-weight files; Lora italic for quotes).
  H3/H4 Montserrat 600/700. UI Montserrat small tracked uppercase (.68–.74rem,
  .08–.22em). Banned: Poppins, Times, Lato, Inter, Roboto.

### Layout, imagery and logos
- Pages are built from the band system in `styles.css` (splitband, navy bands,
  gallery-3, statrow, timeline, pricecols, spectiles, logoband, marquee,
  bandphoto, bandtexture). A page that needs something new adds it to the system.
- Charter and season cards are photo-led, never text-only. Homepage season cards
  stack as full-width rows with a photo beside the copy, the whole row clickable.
- Every page is image-rich. Sections alternate white and Beach Cream; cards are
  Dune Sand or white, soft corners, gentle shadow.
- **`.bandphoto`** (`<section class="navy bandphoto">` + `<picture class="band-bg">`
  first child, scrim built in): full-bleed live-site photo, two per page at most.
  **`.bandtexture`**: same markup with a ~92% cream overlay so a real photo reads
  as faint texture.
- Photos are real Top End catches, country, people and the boat. No stock, no
  clip-art. Light scrims only where text sits.
- Logos: white wordmark on photos and dark panels, black on cream. Render web
  PNGs from the vector PDF, not the supplied ~1182px PNG. The master set and
  its map are held by the Monty skill. Never stretch or recolour; B-Corp and
  "As Seen On" marks sit separately.
- About is its own page (`about-barefoot.html`, keeps the live URL).
- **Angling Adventures is not a nav item.** It appears as a text link in the
  cross-sell strip, the home #adventures section and the footer.

### Copy and calls to action
- Page copy tracks the old live site (exported in the Mac project folder,
  `GHL-content-export/`). Allowed deltas: SEO titles/meta/schema, structural
  headings, light polish, and additions GW approved (testimonials, FAQs, spec
  tiles, cross-sell strip).
- Info-book and course material stays off charter pages: no technique sections,
  tackle specs or "what you'll learn" blocks.
- Fly anglers and lure anglers are different customers: never pitch them together
  on one page.
- No fish measurements in any headline, tagline, hero or section heading.
- Every conversion button reads **"Check dates & enquire"** and points at the
  page's enquiry band. The lead-magnet capture (Black Book etc.) appears once per
  page, in its own band near the foot. The enquiry form has one submit button,
  with call and WhatsApp beside it.
- Positioning, voice and register notes are private: they live in GW's Google
  Drive folder "Barefoot Fishing website build 2025", not here.

### SEO (every page)
- One H1, logical H2/H3. Unique title (≤60 chars) and meta description
  (≤155 chars) around real searches: barramundi fishing Darwin, Darwin fishing
  charters, fly fishing Northern Territory, guided fishing Top End.
- LocalBusiness/TouristAttraction JSON-LD. Descriptive alt on every image.
- Keep old URLs working; changed ones get a redirect in `vercel.json` and a line
  in `pipeline/legacy-paths.txt`.

### Definition of done (before telling GW a page is finished)
1. Every link, button, form and nav item works; 375px, tablet and desktop checked.
2. Brand check: palette only, bundled fonts only, contrast rules met, no orange fills.
3. No invented content: every trip, price, testimonial and contact traces to the
   live site or something GW gave.
4. `prelaunch_audit.py` prints PASS.
5. Report to GW in plain English with clickable links.
