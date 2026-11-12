#!/usr/bin/env python3
"""
Weekly Bag a Barra publisher.

Watty's segment airs Friday on Oz Off Road Radio (3AW / Nine Radio). This finds
any segment in the feed we haven't published yet, transcribes it on-device
(free — never a paid API), builds its page, links it into the Media Centre
archive and the sitemap, commits, and pushes main (Vercel serves main).

    python3 tools/publish_bagabarra.py              # do the lot
    python3 tools/publish_bagabarra.py --dry-run    # say what it would do
    python3 tools/publish_bagabarra.py --no-push    # build + commit, don't push

The feed only ever holds the last 100 items, so a segment that rolls off it is
gone for good. That is the whole reason this runs weekly.

Audio is never rehosted — pages stream from Omny so the publisher keeps their
download numbers. We only store the transcript.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SITE = os.path.join(ROOT, "site")
MASTERS = os.path.join(ROOT, "transcripts-master")
MANIFEST = os.path.join(MASTERS, "episodes-all.json")
BAB_DIR = os.path.join(MASTERS, "bag-a-barra")

FEED = ("https://www.omnycontent.com/d/playlist/"
        "88b564ea-a9a6-4751-910a-a5d800019396/"
        "7bb57587-7f99-4950-a6d1-a99f0041eae6/"
        "37d55f8a-c279-4c5e-9d39-a99f0042fa99/podcast.rss")

# Title spellings have drifted over seven years (Glen/Glenn, Watt/Watts, every
# quote style going), so never match an exact title. The rest of the feed is
# off-road content and must not land on a fishing site.
BAB = re.compile(r"bag a barra|watty|watt\b", re.I)
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

SHOW = "Bag a Barra, Oz Off Road Radio"
STATION = "3AW / Nine Radio"

# Durable transcript folders, searched by basename when the manifest still
# points at a scratchpad that has since been cleaned up.
MASTER_DIRS = [BAB_DIR,
               os.path.join(MASTERS, "abc-fishing-on-arvos"),
               os.path.join(MASTERS, "interviews"),
               os.path.join(MASTERS, "youtube")]

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def log(msg):
    print(msg, flush=True)


def pretty_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} {MONTHS[m - 1]} {y}"


# ---------------------------------------------------------------- the feed

def feed_episodes():
    """Every Bag a Barra item currently in the feed, newest first."""
    raw = urllib.request.urlopen(FEED, timeout=90).read()
    out = []
    for item in ET.fromstring(raw).findall(".//item"):
        title = item.findtext("title") or ""
        if not BAB.search(title):
            continue
        pub = item.findtext("pubDate")
        enc = item.find("enclosure")
        if not pub or enc is None:
            continue
        when = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z")
        date = when.astimezone(timezone.utc).strftime("%Y-%m-%d")
        out.append({
            "slug": f"bag-a-barra-{date}",
            "date": date,
            "title": f"Bag a Barra — {pretty_date(date)}",
            "show": SHOW,
            "station": STATION,
            "audio": enc.get("url"),
            "page": item.findtext("link") or "",
            "dur": _duration(item.findtext(ITUNES + "duration")),
            "transcript": os.path.join(BAB_DIR, f"bag-a-barra-{date}.txt"),
            "kind": "podcast",
            "feed_title": title,
        })
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def _duration(text):
    if not text:
        return 0.0
    if ":" in text:
        parts = [float(p) for p in text.split(":")]
        secs = 0.0
        for p in parts:
            secs = secs * 60 + p
        return secs
    try:
        return float(text)
    except ValueError:
        return 0.0


# ------------------------------------------------------- transcript masters

def resolve_transcripts(eps):
    """Repoint any manifest entry whose transcript path no longer exists.

    The originals were written to a session scratchpad that gets cleaned up;
    the durable copies live in transcripts-master/ under the same basename.
    """
    index = {}
    for d in MASTER_DIRS:
        if os.path.isdir(d):
            for name in os.listdir(d):
                index.setdefault(name, os.path.join(d, name))
    fixed = 0
    for e in eps:
        if os.path.exists(e["transcript"]):
            continue
        found = (index.get(os.path.basename(e["transcript"]))
                 or index.get(e["slug"] + ".txt"))
        if found:
            e["transcript"] = found
            fixed += 1
        else:
            log(f"  !! no transcript master for {e['slug']}")
    if fixed:
        log(f"  repointed {fixed} transcript paths at transcripts-master/")
    return eps


def transcribe(ep, workdir):
    """Download the audio and run the on-device transcriber. Free, offline."""
    binary = os.path.join(TOOLS, "transcribe")
    if not os.path.exists(binary):
        log("  building the transcriber (one-off)")
        subprocess.run(["swiftc", "-O", "-parse-as-library",
                        "transcribe.swift", "-o", "transcribe"],
                       cwd=TOOLS, check=True, capture_output=True)

    audio = os.path.join(workdir, ep["slug"] + ".mp3")
    log(f"  downloading audio")
    req = urllib.request.Request(ep["audio"], headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(audio, "wb") as fh:
        fh.write(r.read())
    log(f"  transcribing ({os.path.getsize(audio) // 1024}KB)")
    res = subprocess.run([binary, audio], capture_output=True, text=True)
    if res.returncode != 0 or len(res.stdout.split()) < 100:
        raise RuntimeError(f"transcription failed: {res.stderr[:400]}")

    os.makedirs(BAB_DIR, exist_ok=True)
    with open(ep["transcript"], "w", encoding="utf-8") as fh:
        fh.write(res.stdout)
    log(f"  {len(res.stdout.split()):,} raw words -> {os.path.relpath(ep['transcript'], ROOT)}")


# --------------------------------------------------------- the archive page

def link_into_archive(ep):
    """Add the segment to the Media Centre's year accordion and bump the counts."""
    path = os.path.join(SITE, "media.html")
    html = open(path, encoding="utf-8").read()
    href = f'media/{ep["slug"]}.html'
    if href in html:
        log("  already in media.html")
        return html, False

    year = ep["date"][:4]
    row = f'          <li><a href="{href}">{pretty_date(ep["date"])}</a></li>\n'

    # Find this year's accordion. A year with no block yet gets a new one.
    block = re.search(r'(<details class="yr"[^>]*>\s*<summary>' + year
                      + r'\s*<span class="cnt">)(\d+)( segments</span></summary>\s*'
                      r'<ul class="eplist">\n)', html)
    if block:
        head = html[:block.end(3)]
        tail = html[block.end(3):]
        html = head + row + tail
        html = html.replace(block.group(0),
                            block.group(1) + str(int(block.group(2)) + 1) + block.group(3), 1)
    else:
        newest = re.search(r'\s*<details class="yr"', html)
        if not newest:
            raise RuntimeError("no year accordion found in media.html")
        acc = (f'      <details class="yr" open>\n'
               f'        <summary>{year} <span class="cnt">1 segments</span></summary>\n'
               f'        <ul class="eplist">\n{row}'
               f'        </ul>\n      </details>\n')
        html = html[:newest.start()] + "\n" + acc + html[newest.start():]
        log(f"  opened a new {year} accordion")

    # The heading carries the running total.
    total = re.search(r'(<h2>Bag a Barra &mdash; )(\d+)( segments</h2>)', html)
    if total:
        html = html.replace(total.group(0),
                            total.group(1) + str(int(total.group(2)) + 1) + total.group(3), 1)

    # The teaser card carries the same number in prose. It was NOT being bumped,
    # so it drifted one behind the heading every time a segment published.
    card = re.search(r'(<strong>Bag a Barra</strong> segment on Oz Off Road Radio '
                     r'&mdash; )(\d+)( of them, back to 2019)', html)
    if card:
        html = html.replace(card.group(0),
                            card.group(1) + str(int(card.group(2)) + 1) + card.group(3), 1)
    else:
        log("  ⚠️  couldn't find the Bag a Barra count in the teaser card — check media.html")

    # Only the newest year stays open.
    opens = list(re.finditer(r'<details class="yr"( open)?>', html))
    for m in reversed(opens[1:]):
        if m.group(1):
            html = html[:m.start()] + '<details class="yr">' + html[m.end():]

    open(path, "w", encoding="utf-8").write(html)
    log(f"  linked into media.html ({year} accordion)")
    return html, True


def add_to_sitemap(ep):
    path = os.path.join(SITE, "sitemap.xml")
    xml = open(path, encoding="utf-8").read()
    loc = f"https://barefootfishingsafaris.com.au/media/{ep['slug']}"
    if loc + "<" in xml:
        log("  already in sitemap.xml")
        return
    row = (f'  <url><loc>{loc}</loc><lastmod>{ep["date"]}</lastmod>'
           f'<priority>0.4</priority></url>\n')
    xml = xml.replace("</urlset>", row + "</urlset>", 1)
    open(path, "w", encoding="utf-8").write(xml)
    log("  added to sitemap.xml")


# ------------------------------------------------------------------ git

def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=SITE, check=check,
                          capture_output=True, text=True)


def publish(message, push=True):
    if not git("status", "--porcelain").stdout.strip():
        log("nothing to commit")
        return
    git("add", "-A")
    git("commit", "-m", message)
    log(f"committed: {message}")
    if not push:
        log("--no-push: left it local")
        return
    # The site moved from GitHub Pages to Vercel at launch (Sep 2026): Vercel
    # serves main as-is, so a push to main is live. No gh-pages branch exists
    # on GitHub any more, so the old main -> gh-pages step is gone.
    git("push", "origin", "main")
    log("pushed main (Vercel puts it live in a minute or two)")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what is new, change nothing")
    ap.add_argument("--no-push", action="store_true",
                    help="build and commit but do not push")
    ap.add_argument("--limit", type=int, default=0,
                    help="only do the N newest missing segments")
    args = ap.parse_args()

    sys.path.insert(0, TOOLS)
    import build_media

    eps = resolve_transcripts(json.load(open(MANIFEST, encoding="utf-8")))
    # Published means the page is actually on disk, not just a manifest row —
    # so a page lost to a revert or a bad build gets rebuilt rather than
    # silently skipped forever.
    known = {e["slug"] for e in eps
             if os.path.exists(os.path.join(SITE, "media", e["slug"] + ".html"))}
    in_manifest = {e["slug"] for e in eps}

    log("checking the feed")
    candidates = feed_episodes()
    missing = [e for e in candidates if e["slug"] not in known]
    # Anything already in the manifest is a rebuild, not a new arrival.
    eps = [e for e in eps if e["slug"] not in {m["slug"] for m in missing}]
    for e in missing:
        if e["slug"] in in_manifest:
            log(f"  page missing for {e['slug']} — rebuilding it")
    log(f"{len(candidates)} segments in the feed, {len(missing)} not published")

    if not missing:
        log("nothing new this week")
        return 0
    for e in missing:
        log(f"  NEW  {e['date']}  {e['feed_title'][:60]}")
    if args.limit:
        missing = missing[:args.limit]
    if args.dry_run:
        log("--dry-run: stopping here")
        return 0

    done = []
    with tempfile.TemporaryDirectory() as work:
        for ep in missing:
            log(f"\n{ep['slug']}")
            try:
                if not os.path.exists(ep["transcript"]):
                    transcribe(ep, work)
                else:
                    log("  transcript already on disk, reusing")
                record = {k: v for k, v in ep.items() if k != "feed_title"}
                eps.append(record)
                done.append(record)
            except Exception as exc:                      # noqa: BLE001
                log(f"  FAILED: {exc}")

    if not done:
        log("\nnothing published")
        return 1

    # One rebuild covers the new pages and refreshes each one's neighbour
    # links, which the arrival of a newer segment changes.
    eps.sort(key=lambda e: e["date"], reverse=True)
    json.dump(eps, open(MANIFEST, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    log(f"\nmanifest now holds {len(eps)} episodes")

    sys.argv = ["build_media.py", SITE, MANIFEST]
    build_media.main()

    for ep in sorted(done, key=lambda e: e["date"]):
        log(f"\nlinking {ep['slug']}")
        link_into_archive(ep)
        add_to_sitemap(ep)

    what = ", ".join(pretty_date(e["date"]) for e in sorted(done, key=lambda e: e["date"]))
    publish(f"Bag a Barra: publish {what}", push=not args.no_push)
    log(f"\ndone — {len(done)} segment(s) live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
