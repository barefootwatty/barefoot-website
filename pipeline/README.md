# Pipeline (not part of the website)

Every script that builds a page lives in `tools/`. Which script builds which
page is mapped in `CLAUDE.md` at the repo root. Since 12 Nov 2026 that includes
the radio/topic builders (`build_media.py`, `build_topics.py`,
`clean_transcript.py`), the weekly `publish_bagabarra.py` with its Mac
transcriber `transcribe.swift`, and `add_social_meta.py`. Before that they lived
only on GW's Mac.

Everything the weekly article job needs to run without Glenn's Mac: the build
scripts, the lesson list (articles/manifest.json), the verified place-name list and
the article sources. `.vercelignore` keeps this folder off the live site.

The scripts expect the layout `ROOT/{tools,articles,site}`. In a fresh checkout:

    mkdir -p /tmp/work && cp -r pipeline/tools pipeline/articles /tmp/work/
    ln -s "$PWD" /tmp/work/site
    cd /tmp/work && python3 tools/check_places.py && python3 tools/build_article.py articles/src/<slug>.txt

Then copy any new `articles/src/*.txt` and `articles/placenames.txt` back into
`pipeline/articles/` before committing.

---

# Trip dates and availability

`assets/availability.json` is the one place trip dates live. After any change:

    python3 pipeline/tools/build_availability.py .

Run it inside the website folder (on the Mac that is the `site` folder). This is
the only copy of the script: an older `tools/build_availability.py` outside the
repo does not know about `held` and must not be used. It rewrites the `AVAIL:LIST` and `AVAIL:PICKER` blocks on the home,
run-off, fly and Bynoe/Dundee pages. Never edit those blocks by hand. Then commit
and push to `main`. Vercel serves the repo as-is, so a push to `main` is live. The
enquiry auto-reply (`api/enquiry.js`) reads the JSON live, so it follows the site.

## Held dates

Rule: every time an invoice is sent, those dates show as **Held · deposit
pending** on the website and in the auto-reply until the deposit lands or the
14-day hold lapses.

| When | Set on the window | Then |
|---|---|---|
| Invoice sent | `"status": "held"`, `"held_until": "YYYY-MM-DD"` (invoice date + 14 days) | rebuild, push |
| Deposit paid | `"status": "booked"`, remove `held_until` | rebuild, push |
| Hold lapsed, no deposit | `"status": "open"`, remove `held_until` | rebuild, push |

- If the invoice covers only part of a listed window, split the window in two:
  the invoiced days `held`, the rest `open` (or `held` too if Watty does not want
  the leftover days sold separately).
- `held_until` is a private note. It is never written into a page or an email.
  Nothing releases a hold automatically: the build script prints `HOLD LAPSED`
  for any hold past its date, and a person decides.
- The summary bar is counted in days, not windows: "% booked" is booked days out
  of all days listed, "N of M days still open" is open days. A held window is
  neither. The auto-reply does the same sum, so the email and the site agree.
- Tapping a held tile on the enquiry form joins the waitlist, same as a booked one.
- **No client names** in `availability.json`, the pages, the auto-reply or a
  commit message. The JSON and this GitHub repo are public. Dates and status
  only. Client names and trip details live in the Barefoot calendar and nowhere
  else. The script refuses to build if a
  window carries any field other than trip, start, end, status, held_until.
- Set `"updated"` to the day of the change.
- Most visitors are on a phone: look at any change to the date list, the tiles
  or the enquiry form at phone width before it goes live.

## Enquiry form

The form is on the home, run-off, fly and Bynoe/Dundee pages. Name, email and
mobile number are all required (the mobile since Nov 2026): the page checks
them, and `api/enquiry.js` refuses an enquiry without them.
