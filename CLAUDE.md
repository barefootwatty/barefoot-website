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
