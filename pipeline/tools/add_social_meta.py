#!/usr/bin/env python3
"""Give every page a canonical URL and a proper social preview.

Run from the project root:  python3 tools/add_social_meta.py [--dry-run]

WHY: before this, 299 pages had no <link rel="canonical"> and 288 had no
og:image, so sharing a transcript or article on Facebook, WhatsApp or iMessage
showed a bare grey box. The canonical also stops the gh-pages preview being
indexed as a duplicate of the real site.

Idempotent — safe to re-run. It only adds tags a page doesn't already have.

⭐ The same tags are emitted by build_media.py / build_topics.py /
build_article.py. If you change one, change all four, or the next rebuild
silently reverts 280+ pages.
"""

import os
import re
import sys

SITE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"))
BASE = "https://barefootfishingsafaris.com.au"
SHARE_IMAGE = f"{BASE}/assets/img/run-off-barra-hero-1600.jpg"
SHARE_ALT = "A barramundi held boatside on a Top End run-off morning"
SITE_NAME = "Barefoot Fishing Safaris"

DESC = re.compile(r'<meta\s+name="description"\s+content="(.*?)"\s*/?>', re.I | re.S)
OGTITLE = re.compile(r'<meta\s+property="og:title".*?>', re.I | re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)


def canonical_for(relpath):
    """cleanUrls is on in vercel.json, so the live URL has no .html suffix."""
    slug = relpath.replace(os.sep, "/")
    if slug == "index.html":
        return BASE + "/"
    return f"{BASE}/{slug[:-5]}" if slug.endswith(".html") else f"{BASE}/{slug}"


def pages():
    for dirpath, dirnames, filenames in os.walk(SITE):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in sorted(filenames):
            if name.endswith(".html") and name != "404.html":
                yield os.path.join(dirpath, name)


def main():
    dry = "--dry-run" in sys.argv
    touched = 0

    for path in pages():
        rel = os.path.relpath(path, SITE)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

        url = canonical_for(rel)
        desc_match = DESC.search(text)
        desc = desc_match.group(1).strip() if desc_match else ""
        title_match = TITLE.search(text)
        title = title_match.group(1).strip() if title_match else SITE_NAME

        add = []
        if 'rel="canonical"' not in text:
            add.append(f'<link rel="canonical" href="{url}">')
        if "og:url" not in text:
            add.append(f'<meta property="og:url" content="{url}">')
        if "og:site_name" not in text:
            add.append(f'<meta property="og:site_name" content="{SITE_NAME}">')
        if "og:title" not in text:
            add.append(f'<meta property="og:title" content="{title}">')
        if "og:description" not in text and desc:
            add.append(f'<meta property="og:description" content="{desc}">')
        if "og:image" not in text:
            add.append(f'<meta property="og:image" content="{SHARE_IMAGE}">')
            add.append(f'<meta property="og:image:alt" content="{SHARE_ALT}">')
        if "twitter:card" not in text:
            add.append('<meta name="twitter:card" content="summary_large_image">')

        if not add:
            continue

        block = "\n".join(add)

        # Anchor the block right after the existing og:title if there is one,
        # otherwise after the description, otherwise after the <title>.
        anchor = OGTITLE.search(text) or desc_match or title_match
        end = anchor.end()
        text = text[:end] + "\n" + block + text[end:]

        touched += 1
        if not dry:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

    print(f"{'Would update' if dry else 'Updated'} {touched} page(s)")


if __name__ == "__main__":
    main()
