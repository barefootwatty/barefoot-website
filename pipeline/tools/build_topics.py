"""
Build the topic index from the transcripts.

249 dated episode pages are hard to enter from a search engine — nobody
searches "Bag a Barra, 14 March 2025". They search "Shady Camp run-off tide".
This turns the corpus inside out: one page per subject, carrying the actual
sentences Watty said about it, each linked back to the episode it came from.

Topics are curated, not auto-extracted. The frequency scan threw up plenty of
terms that look good and aren't: "barra" appears in 201 of 249 episodes (it's
the whole site, not a topic) and "cod" is Murray Cod — southern callers to the
radio show, nothing to do with the Top End.

    python3 build_topics.py <site_dir> <episodes.json>
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_transcript import clean
from sitemeta import head_meta

CSS_V = "v=25"

# (slug, display name, regex, blurb). Ordered within category by usefulness.
TOPICS = {
    "Places": [
        ("dundee", "Dundee", r"\bdundee\b", "Dundee Beach and the country either side of it."),
        ("kakadu", "Kakadu", r"\bkakadu\b", "Fishing inside the park — permits, seasons and the systems that matter."),
        ("darwin-harbour", "Darwin Harbour", r"\bdarwin harbour\b", "The harbour on Watty's doorstep, and how it fishes through the year."),
        ("south-alligator", "South Alligator", r"\bsouth alligator\b", "One of Kakadu's big tidal systems."),
        ("shady-camp", "Shady Camp", r"\bshady camp\b", "The barrage, the tides and why it fishes the way it does."),
        ("east-alligator", "East Alligator", r"\beast alligator\b", "Cahills Crossing country and the East Alligator run."),
        ("adelaide-river", "Adelaide River", r"\badelaide river\b", "Close to town, and a system with its own rules."),
        ("mary-river", "Mary River", r"\bmary river\b", "Mary River system — floodplain, barrage and coastal reaches."),
        ("daly-river", "Daly River", r"\bdaly river\b", "The Daly, and the April run that draws everyone."),
    ],
    "Seasons, tides and water": [
        ("wet-season", "The wet season", r"\bwet season\b", "What the wet does to the country and the fishing."),
        ("dry-season", "The dry season", r"\bdry season\b", "Clearer water, harder fish, different game."),
        ("run-off", "The run-off", r"\brun[- ]?off\b", "The season Barefoot is built around — water coming off the floodplain."),
        ("billabongs", "Billabongs", r"\bbillabong", "Landlocked water, and what lives in it."),
        ("build-up", "The build-up", r"\bbuild[- ]?up\b", "Hot, still and building — the lead-in to the wet."),
        ("floodplain", "The floodplain", r"\bfloodplain", "Where the water goes, and what follows it."),
        ("monsoon", "Monsoon and weather", r"\bmonsoon\b", "Monsoon troughs, big weather, and fishing around it."),
        ("moon-and-tides", "Moon and tides", r"\b(full moon|new moon|spring tide|neap|king tide)\b",
         "Springs, neaps and the moon — the pillar that decides most Top End sessions."),
    ],
    "How to fish it": [
        ("fly-fishing", "Fly fishing", r"\bfly fishing\b", "Fly in the Top End — where it works and where it doesn't."),
        ("casting", "Casting", r"\bcasting\b", "Placing a lure where it needs to be."),
        ("snags", "Fishing the snags", r"\bsnag", "Timber, structure and getting fish out of it."),
        ("vibes", "Vibes and soft plastics", r"\b(vibe|soft plastic|paddle tail)\b", "Sinking lures and how Watty works them."),
        ("trolling", "Trolling", r"\btrolling\b", "When trolling beats casting, and why."),
    ],
    "What you'll catch": [
        ("saratoga", "Saratoga", r"\bsaratoga\b", "Freshwater surface fish with a bad attitude."),
        ("queenfish", "Queenfish", r"\bqueenfish\b", "Fast, aerial and everywhere in the dry."),
        ("golden-snapper", "Golden snapper", r"\b(golden snapper|fingermark)\b", "Fingermark — structure fish worth targeting."),
        ("threadfin", "Threadfin salmon", r"\bthreadfin\b", "The other barra — and often the better eating."),
        ("tarpon", "Tarpon", r"\btarpon\b", "Small, tough and perfect on light gear."),
        ("sharks", "Sharks", r"\bshark", "Taxmen, and how to fish around them."),
        ("trevally", "Trevally", r"\btrevally\b", "GTs and their cousins on the blue water."),
    ],
    "On the water": [
        ("boat-ramps", "Boat ramps", r"\bboat ramp", "Ramps, tides and not getting stuck."),
        ("safety", "Safety", r"\b(lifejacket|life jacket|safety gear|epirb|flares)\b", "Crocs, weather and coming home."),
        ("rigging", "Hooks, leader and rigging", r"\b(leader|trebles|hooks|rigging)\b", "Terminal tackle that survives a barra."),
    ],
}

HERO = {
    "Places": ("band-bynoe-flats-drone", 1600, 1200),
    "Seasons, tides and water": ("band-video-flats-drone", 1600, 1066),
    "How to fish it": ("band-enquire-topdown-turquoise", 1600, 900),
    "What you'll catch": ("band-bynoe-creek-texture", 1600, 900),
    "On the water": ("band-pricing-glass-river", 1600, 1066),
}


def _excerpt(text, pattern, lo_len=90, hi_len=340):
    """Best sentence mentioning the topic — not merely the first.

    First-mention grabbing produced fragments like "Now, this is a Shady Camp."
    and quotes that had drifted off the term entirely. So: walk every mention,
    take the sentence around it with real boundaries, keep only those that
    still contain the term and read as a whole thought, and return the meatiest.
    """
    best = None
    for m in re.finditer(pattern, text, re.I):
        lo = text.rfind(".", 0, m.start()) + 1
        hi = text.find(".", m.end())
        hi = len(text) if hi == -1 else hi + 1
        frag = text[lo:hi].strip()

        # a very short sentence on its own says nothing — pull in the next one
        if len(frag) < lo_len:
            hi2 = text.find(".", hi)
            if hi2 != -1:
                frag = text[lo:hi2 + 1].strip()

        if not (lo_len <= len(frag) <= hi_len):
            continue
        if not re.search(pattern, frag, re.I):
            continue          # boundary drifted off the term
        if frag[0].islower():
            continue          # started mid-thought
        if len(best[1]) if best else 0:
            pass
        if best is None or len(frag) > len(best[1]):
            best = (0, frag)
    return best[1] if best else None


def _shell(title, desc, hero, eyebrow, h1, sub, body, prefix="../", relpath="index.html"):
    slug, w, h = hero
    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" type="image/png" href="{prefix}assets/fish-icon.png">
<link rel="stylesheet" href="{prefix}styles.css?{CSS_V}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(h1)}">
{head_meta(relpath, desc)}
</head>
<body>

<header class="site">
  <nav class="nav">
    <a href="{prefix}index.html"><img src="{prefix}assets/logo-white.png" alt="Barefoot Fishing Safaris"></a>
    <button class="nav-toggle" aria-label="Menu" aria-expanded="false" onclick="var u=document.getElementById('navmenu');u.classList.toggle('open');this.setAttribute('aria-expanded',u.classList.contains('open'))">&#9776;</button>
    <ul id="navmenu">
      <li><a href="{prefix}index.html">Home</a></li>
      <li><a href="{prefix}index.html#safaris">Safaris</a></li>
      <li><a href="{prefix}media.html">Media</a></li>
      <li><a href="{prefix}gallery.html">Gallery</a></li>
      <li><a href="{prefix}about-barefoot.html">About</a></li>
      <li><a href="{prefix}index.html#contact" class="btn btn-primary">Book a Trip</a></li>
    </ul>
  </nav>
</header>

<section class="subhero photohero tall">
  <picture class="hero-bg">
    <source type="image/avif" srcset="{prefix}assets/img/{slug}-640.avif 640w, {prefix}assets/img/{slug}-1000.avif 1000w, {prefix}assets/img/{slug}-1600.avif 1600w" sizes="100vw">
    <img src="{prefix}assets/img/{slug}-1600.jpg" srcset="{prefix}assets/img/{slug}-640.jpg 640w, {prefix}assets/img/{slug}-1000.jpg 1000w, {prefix}assets/img/{slug}-1600.jpg 1600w" sizes="100vw" width="{w}" height="{h}" alt="" fetchpriority="high" decoding="async">
  </picture>
  <div class="hero-content">
    <p class="eyebrow">{eyebrow}</p>
    <div class="hero-titlerow">
      <svg class="hero-fish" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12c2.5-4 8-6 13-3.5 2.2 1.1 3.5 2.3 3.5 3.5s-1.3 2.4-3.5 3.5C11 18 5.5 16 3 12z"/><path d="M19.5 12L23 8v8z"/><circle cx="7" cy="10.8" r=".7"/></svg>
      <h1>{html.escape(h1)}</h1>
    </div>
    <p class="hero-sub quiet">{sub}</p>
  </div>
</section>

{body}

<footer class="site">
  <div class="wrap">
    <div class="foot-note">
      <span>&copy; <span class="copyyear">2026</span><script>document.currentScript.previousSibling.textContent=new Date().getFullYear()</script> Barefoot Fishing Safaris &middot; Coolalinga, Northern Territory &middot; <a href="{prefix}privacy-policy.html" style="color:inherit">Privacy</a> &middot; <a href="{prefix}booking-terms.html" style="color:inherit">Booking terms</a></span>
      <span>Fish with Watty &middot; 0417 272 871</span>
    </div>
  </div>
</footer>

</body>
</html>
"""


def main():
    site_dir, feed = sys.argv[1], sys.argv[2]
    eps = json.load(open(feed, encoding="utf-8"))
    texts, meta = {}, {}
    for e in eps:
        if not os.path.exists(e["transcript"]):
            continue
        paras, _ = clean(open(e["transcript"], encoding="utf-8", errors="replace").read())
        texts[e["slug"]] = " ".join(paras)
        meta[e["slug"]] = e

    out_dir = os.path.join(site_dir, "topics")
    os.makedirs(out_dir, exist_ok=True)
    built, index_rows = [], {}

    for cat, topics in TOPICS.items():
        index_rows[cat] = []
        for slug, name, pat, blurb in topics:
            hits = []
            for s, tx in texts.items():
                ex = _excerpt(tx, pat)
                if ex:
                    hits.append((meta[s], ex))
            if len(hits) < 5:
                print(f"  skip (only {len(hits)} episodes): {name}")
                continue
            hits.sort(key=lambda h: h[0]["date"], reverse=True)

            items = "\n".join(
                f'''      <li class="tq">
        <blockquote>{html.escape(ex)}</blockquote>
        <p class="src"><a href="../media/{e["slug"]}.html">{html.escape(e["title"])}</a>
          <span>{html.escape(e.get("show", ""))}</span></p>
      </li>''' for e, ex in hits)

            body = f'''<section>
  <div class="wrap">
    <div class="section-head">
      <h2>{len(hits)} times Watty has talked about this</h2>
      <p>{blurb} Every quote below is from a real segment &mdash; follow it through for the audio and the full transcript.</p>
    </div>
    <ul class="tqlist">
{items}
    </ul>
    <p class="epmeta" style="margin-top:2.6rem"><a href="../topics.html">&larr; All topics</a> &nbsp;&middot;&nbsp; <a href="../media.html#archive">The whole archive</a></p>
  </div>
</section>'''

            page = _shell(
                title=f"{name} &mdash; what Watty says | Barefoot Fishing Safaris",
                desc=f"{blurb} Drawn from {len(hits)} radio segments and podcast appearances by Top End guide Glenn \"Watty\" Watt, each with audio and a full transcript.",
                hero=HERO[cat], eyebrow=cat, h1=name,
                sub=f"From {len(hits)} segments across the archive.", body=body,
                relpath=f"topics/{slug}.html")
            with open(os.path.join(out_dir, slug + ".html"), "w", encoding="utf-8") as fh:
                fh.write(page)
            built.append(slug)
            index_rows[cat].append((slug, name, len(hits), blurb))

    # index page
    blocks = []
    for cat, rows in index_rows.items():
        if not rows:
            continue
        cards = "\n".join(
            f'''      <a class="card sand epcard" href="topics/{slug}.html">
        <div class="season">{n} segments</div>
        <h3>{html.escape(name)}</h3>
        <p>{html.escape(blurb)}</p>
        <span class="go">Read what he said &rarr;</span>
      </a>''' for slug, name, n, blurb in rows)
        blocks.append(f'''<section class="{'cream' if len(blocks) % 2 else ''}">
  <div class="wrap">
    <div class="section-head"><h2>{html.escape(cat)}</h2></div>
    <div class="grid grid-3">
{cards}
    </div>
  </div>
</section>''')

    idx = _shell(
        title="Topics &mdash; Everything Watty Has Said, By Subject | Barefoot Fishing Safaris",
        desc="Seven years of Top End fishing radio, sorted by subject: Kakadu, Shady Camp, the run-off, tides, fly fishing, saratoga and more. Every topic links to the audio and full transcripts.",
        hero=("band-texture-flats", 1600, 1200), eyebrow="By subject",
        h1="What Watty says about…",
        sub="Seven years of radio, sorted by what he was actually talking about.",
        body="\n\n".join(blocks), prefix="", relpath="topics.html")
    with open(os.path.join(site_dir, "topics.html"), "w", encoding="utf-8") as fh:
        fh.write(idx)

    print(f"built {len(built)} topic pages + topics.html")
    return built


if __name__ == "__main__":
    main()
