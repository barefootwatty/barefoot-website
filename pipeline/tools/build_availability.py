#!/usr/bin/env python3
"""
Rewrite the availability blocks on the website from assets/availability.json.

    python3 tools/build_availability.py site            (Mac project layout)
    python3 pipeline/tools/build_availability.py .      (from a repo checkout)

The one argument is the folder that holds index.html. Only the text between
the <!-- AVAIL:LIST --> / <!-- AVAIL:PICKER --> markers is touched, so running
it twice changes nothing the second time.

STATUS VALUES (set per window in availability.json)
  open    on sale                      list "Available"               tile "Open"
  held    invoice sent, deposit not    list "Held · deposit pending"  tile "Held"
          yet paid                     (tapping the tile joins the waitlist)
  booked  deposit paid                 list "Booked"                  tile "Waitlist"

A held window may carry "held_until": "YYYY-MM-DD" (invoice date + 14 days).
That field is a note for us only: it is never written into a page. Running
this script prints any hold that has lapsed so it can be released or chased.

The summary bar counts "booked" only for the percentage and "open" only for
"N of M windows still open", so a held window is neither.

NEVER put a client's name in availability.json: it is a public file.
"""
import html
import json
import os
import re
import sys
from datetime import date

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# status -> (css class, date-list label, tile label, tile joins the waitlist?)
STATUS = {
    "open":   ("open", "Available", "Open", False),
    "held":   ("held", "Held &middot; deposit pending", "Held", True),
    "booked": ("gone", "Booked", "Waitlist", True),
}

# Which trips each page shows, and its own wording for the list heading.
#   trips    None = every trip in the file
#   heading  date-list heading after the year ({place} = the trip's place)
#   loc      show the short location beside each date (mixed-trip lists)
PAGES = {
    "index.html": {"trips": None},
    "run-off-barra-fishing.html": {"trips": ["runoff"], "heading": "run-off dates &middot; {place}"},
    "dundee-bynoe-barra-bluewater.html": {"trips": ["bynoe"], "heading": "dates &middot; {place}"},
    "fly-fishing-darwin.html": {"trips": None, "heading": "fly dates &middot; Kakadu run-off, then Bynoe",
                                "loc": True},
}

BLOCK = re.compile(r"^([ \t]*)<!-- AVAIL:(LIST|PICKER) —[^\n]*-->\n.*?^[ \t]*<!-- /AVAIL:\2 -->",
                   re.S | re.M)
NOTE = "generated from assets/availability.json by tools/build_availability.py. Don't edit here."


def esc(text):
    return html.escape(text, quote=False)


def dm(iso):
    _, m, d = (int(x) for x in iso.split("-"))
    return d, m


def long_range(w, dash):
    """18 – 20 March, or 30 May – 1 June across a month end."""
    (ad, am), (bd, bm) = dm(w["start"]), dm(w["end"])
    if am == bm:
        return f"{ad} {dash} {bd} {MONTHS[bm - 1]}"
    return f"{ad} {MONTHS[am - 1]} {dash} {bd} {MONTHS[bm - 1]}"


def short_range(w):
    """18–20 Mar, or 30 May–1 Jun — the compact form on the tiles."""
    (ad, am), (bd, bm) = dm(w["start"]), dm(w["end"])
    if am == bm:
        return f"{ad}&ndash;{bd} {MONTHS[bm - 1][:3]}"
    return f"{ad} {MONTHS[am - 1][:3]}&ndash;{bd} {MONTHS[bm - 1][:3]}"


def bar(av, wins, trips, dark):
    booked = sum(1 for w in wins if w["status"] == "booked")
    still_open = sum(1 for w in wins if w["status"] == "open")
    pct = int(100 * booked / len(wins) + 0.5) if wins else 0
    what = f" {av['trips'][trips[0]]['name'].lower()}" if trips and len(trips) == 1 else ""
    return (f'<div class="avbar{" dark" if dark else ""}" data-av-bar><div class="avbar-track">'
            f'<span style="width:{pct}%"></span></div><p><strong>{av["year"]}{what} is {pct}% booked</strong>'
            f' &middot; {still_open} of {len(wins)} windows still open.'
            f' The best tides often book out up to two years ahead.</p></div>')


def build_list(av, cfg, wins):
    trips = cfg["trips"]
    place = esc(av["trips"][trips[0]]["place"]) if trips and len(trips) == 1 else ""
    out = ['<div class="dates">',
           f'  <p class="soldout">{esc(av["previous_year"]).replace("—", "&mdash;")}</p>',
           f'  <p class="yr">{av["year"]} {cfg["heading"].format(place=place)}</p>',
           '  <ul>']
    for w in wins:
        cls, label, _, _ = STATUS[w["status"]]
        loc = f'<span class="loc">{esc(av["trips"][w["trip"]]["loc"])}</span>' if cfg.get("loc") else ""
        out.append(f'    <li class="{cls}" data-end="{w["end"]}"><span class="d">{long_range(w, "&ndash;")}</span>'
                   f'{loc}<span class="st">{label}</span></li>')
    out += ['  </ul>', '  ' + bar(av, wins, trips, dark=True), '</div>']
    return out


def build_picker(av, cfg, wins):
    trips = cfg["trips"] or list(av["trips"])
    out = ['<fieldset class="avpick" data-avpick>',
           '  <legend>Tap the dates you want</legend>',
           '  <p class="avkey"><span class="k open"></span>Open <span class="k few"></span>Last ones '
           '<span class="k held"></span>Held &mdash; deposit pending '
           '<span class="k gone"></span>Booked &mdash; tap to join the waitlist</p>',
           '  ' + bar(av, wins, cfg["trips"], dark=False)]
    for key in trips:
        t = av["trips"][key]
        out.append(f'  <p class="avgroup">{esc(t["name"])} &middot; {esc(t["place"])}</p>')
        out.append('  <div class="avtiles">')
        for w in (w for w in wins if w["trip"] == key):
            cls, _, tile, waitlist = STATUS[w["status"]]
            label = (f'{"Waitlist: " if waitlist else ""}{long_range(w, "–")} {w["start"][:4]}'
                     f' · {esc(t["name"])}, {esc(t["place"])}')
            out.append(f'    <button type="button" class="avtile {cls}" data-end="{w["end"]}" data-label="{label}"'
                       f' aria-pressed="false"><span class="d">{short_range(w)}</span>'
                       f'<span class="s">{tile}</span></button>')
        out.append('  </div>')
    nxt = av["year"] + 1
    out += ['  <p class="avgroup">Planning further out?</p>',
            '  <div class="avtiles">',
            f'    <button type="button" class="avtile next" data-label="{nxt} — keen to get in early"'
            f' aria-pressed="false"><span class="d">{nxt}</span><span class="s">Get in early</span></button>',
            '  </div>',
            '</fieldset>']
    return out


def check(av):
    """Refuse to build from a file that would publish something wrong."""
    errors = []
    for i, w in enumerate(av["windows"], 1):
        where = f"window {i} ({w.get('start')} to {w.get('end')})"
        if w.get("status") not in STATUS:
            errors.append(f"{where}: status must be open, held or booked, not {w.get('status')!r}")
        if w.get("trip") not in av["trips"]:
            errors.append(f"{where}: unknown trip {w.get('trip')!r}")
        try:
            if date.fromisoformat(w["start"]) > date.fromisoformat(w["end"]):
                errors.append(f"{where}: starts after it ends")
            if "held_until" in w:
                date.fromisoformat(w["held_until"])
        except (KeyError, ValueError):
            errors.append(f"{where}: dates must be YYYY-MM-DD")
        extra = set(w) - {"trip", "start", "end", "status", "held_until"}
        if extra:
            errors.append(f"{where}: unexpected field(s) {sorted(extra)} — this file is public, "
                          "dates and status only, no client names")
        if "held_until" in w and w.get("status") != "held":
            errors.append(f"{where}: has held_until but status is {w.get('status')!r} — remove held_until")
    return errors


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: build_availability.py <site folder>")
    site = sys.argv[1]
    with open(os.path.join(site, "assets", "availability.json"), encoding="utf-8") as f:
        av = json.load(f)

    errors = check(av)
    if errors:
        sys.exit("availability.json needs fixing, nothing was changed:\n" + "\n".join(" - " + e for e in errors))

    changed = 0
    for page, cfg in PAGES.items():
        path = os.path.join(site, page)
        with open(path, encoding="utf-8") as f:
            before = f.read()
        wins = [w for w in av["windows"] if cfg["trips"] is None or w["trip"] in cfg["trips"]]

        def swap(m):
            indent, kind = m.group(1), m.group(2)
            body = build_list(av, cfg, wins) if kind == "LIST" else build_picker(av, cfg, wins)
            lines = [f"<!-- AVAIL:{kind} — {NOTE} -->"] + body + [f"<!-- /AVAIL:{kind} -->"]
            return "\n".join(indent + line for line in lines)

        after, n = BLOCK.subn(swap, before)
        if not n:
            sys.exit(f"{page}: no AVAIL markers found — nothing was changed on this page")
        if after != before:
            with open(path, "w", encoding="utf-8") as f:
                f.write(after)
            changed += 1
        print(f"{page}: {n} block(s) {'updated' if after != before else 'already up to date'}")

    today = date.today().isoformat()
    held = [w for w in av["windows"] if w["status"] == "held"]
    for w in held:
        until = w.get("held_until")
        if not until:
            print(f"NOTE: {w['start']} to {w['end']} is held with no held_until date")
        elif until < today:
            print(f"HOLD LAPSED: {w['start']} to {w['end']} was held until {until} — "
                  "deposit paid? set booked. Not paid? set open (and remove held_until).")
    print(f"done: {changed} page(s) rewritten, {len(held)} window(s) held")


if __name__ == "__main__":
    main()
