#!/usr/bin/env python3
"""Pre-launch audit for the Barefoot site.

Checks every built page for the things that break quietly after go-live:
broken internal links, missing assets, dead anchors, missing alt text, and
the head metadata that search and answer engines rely on.

    python3 tools/prelaunch_audit.py            # from the project root

⚠️ Strip BOTH ?query and #fragment off a href before testing it on disk.
A previous version of this check flagged all 299 `styles.css?v=21` links as
broken and cost a whole cycle chasing nothing.
"""

import os
import re
import sys
from collections import defaultdict
from urllib.parse import unquote

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
ROOT = os.path.normpath(ROOT)

HREF = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.I)
SRCSET = re.compile(r'srcset\s*=\s*"([^"]+)"', re.I)
ID = re.compile(r'\bid\s*=\s*"([^"]+)"')
IMG = re.compile(r"<img\b[^>]*>", re.I)
# A bare "<img>" inside an HTML comment (the "how to add a logo" note on four
# pages) was reported as missing alt text four times before this.
COMMENT = re.compile(r"<!--.*?-->", re.S)
ALT = re.compile(r'\balt\s*=\s*"')
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "javascript:", "data:", "sms:")


def pages():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in sorted(filenames):
            if name.endswith(".html") and name != "404.html" and not name.endswith(".bak"):
                yield os.path.join(dirpath, name)


def rel(path):
    return os.path.relpath(path, ROOT)


def target_of(href):
    """Split a href into (path, fragment), dropping any ?query."""
    href = href.split("#", 1)
    frag = href[1] if len(href) > 1 else ""
    path = href[0].split("?", 1)[0]
    return unquote(path), frag


def main():
    ids = {}
    docs = {}
    for path in pages():
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        docs[path] = text
        ids[rel(path)] = set(ID.findall(text))

    broken = []
    dead_anchors = []
    no_alt = defaultdict(int)
    missing_meta = defaultdict(list)

    for path, text in docs.items():
        here = rel(path)
        base = os.path.dirname(path)

        links = HREF.findall(text)
        for value in SRCSET.findall(text):
            for part in value.split(","):
                part = part.strip().split(" ")[0]
                if part:
                    links.append(part)

        for href in links:
            if not href or href.startswith(SKIP_SCHEMES):
                continue
            target, frag = target_of(href)

            if not target:                      # same-page anchor
                if frag and frag not in ids[here]:
                    dead_anchors.append(f"{here} -> #{frag}")
                continue

            if target.startswith("/"):
                resolved = os.path.join(ROOT, target.lstrip("/"))
            else:
                resolved = os.path.normpath(os.path.join(base, target))

            candidates = [resolved]
            if not os.path.splitext(resolved)[1]:      # cleanUrls: /page -> page.html
                candidates.append(resolved + ".html")
                candidates.append(os.path.join(resolved, "index.html"))

            hit = next((c for c in candidates if os.path.exists(c)), None)
            if hit is None:
                broken.append(f"{here} -> {href}")
                continue

            if frag and hit.endswith(".html"):
                other = rel(hit)
                if other in ids and frag not in ids[other]:
                    dead_anchors.append(f"{here} -> {href}")

        for tag in IMG.findall(COMMENT.sub("", text)):
            if not ALT.search(tag):
                no_alt[here] += 1

        for label, needle in (
            ("title", "<title>"),
            ("description", 'name="description"'),
            ("canonical", 'rel="canonical"'),
            ("og:title", 'og:title'),
            ("og:image", 'og:image'),
        ):
            if needle not in text:
                missing_meta[label].append(here)

    total = len(docs)
    print(f"Audited {total} pages in {ROOT}\n")

    def report(label, items, limit=15):
        print(f"{label}: {len(items)}")
        for item in items[:limit]:
            print(f"    {item}")
        if len(items) > limit:
            print(f"    ... and {len(items) - limit} more")
        print()

    report("Broken internal links/assets", sorted(set(broken)))
    report("Dead anchors", sorted(set(dead_anchors)))
    report("Pages with an img missing alt", sorted(no_alt))
    for label in ("title", "description", "canonical", "og:title", "og:image"):
        report(f"Pages missing {label}", sorted(missing_meta[label]))

    hard = len(set(broken)) + len(set(dead_anchors)) + len(missing_meta["title"]) + len(missing_meta["description"])
    if hard:
        print(f"FAIL — {hard} hard problems")
        return 1
    print("PASS — no broken links, no dead anchors, every page titled and described")
    return 0


if __name__ == "__main__":
    sys.exit(main())
