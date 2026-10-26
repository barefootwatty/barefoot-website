"""One source of truth for the canonical + social tags in every page head.

⭐ THE LESSON THAT KEEPS BITING: anything applied to built pages by a site-wide
script MUST also come out of the generators, or the next rebuild silently
reverts hundreds of pages. So build_media.py, build_topics.py, build_article.py
and add_social_meta.py all call head_meta() here rather than each carrying
their own copy of the tags.

Without these, sharing a transcript on Facebook or WhatsApp showed a bare grey
box, and the gh-pages preview was free to be indexed as a duplicate of the
real site.
"""

BASE = "https://barefootfishingsafaris.com.au"
SITE_NAME = "Barefoot Fishing Safaris"
SHARE_IMAGE = f"{BASE}/assets/img/run-off-barra-hero-1600.jpg"
SHARE_ALT = "A barramundi held boatside on a Top End run-off morning"


def canonical_url(relpath):
    """Live URL for a built page. cleanUrls is on in vercel.json, so no .html."""
    slug = relpath.replace("\\", "/").lstrip("./")
    if slug == "index.html":
        return BASE + "/"
    if slug.endswith(".html"):
        slug = slug[:-5]
    return f"{BASE}/{slug}"


def head_meta(relpath, description="", image=None, indent=""):
    """The canonical + Open Graph block, minus og:type and og:title, which the
    callers set themselves (article vs website, and their own titles)."""
    url = canonical_url(relpath)
    tags = [
        f'<link rel="canonical" href="{url}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:locale" content="en_AU">',
    ]
    if description:
        tags.append(f'<meta property="og:description" content="{description}">')
    tags.append(f'<meta property="og:image" content="{image or SHARE_IMAGE}">')
    if not image:
        tags.append(f'<meta property="og:image:alt" content="{SHARE_ALT}">')
    tags.append('<meta name="twitter:card" content="summary_large_image">')
    return "\n".join(indent + t for t in tags)
