"""
Generate one page per media item: audio player + collapsed transcript.

There are 228 Bag a Barra segments plus the ABC spots, so these pages are
generated, never hand-written — same durability rule as the band system.
Re-running rebuilds every page from the raw transcripts, so a GLOSSARY fix
in clean_transcript.py reflows through the whole archive.

    python3 build_media.py <site_dir> <episodes.json>

episodes.json: [{slug,title,date,show,station,audio,page,transcript,dur}]
`audio` may be a remote URL (podcast, streamed from the publisher) or a
site-relative path (the ABC files, which we host).
"""
import datetime
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_transcript import clean
from sitemeta import head_meta

# Keep in step with the version the rest of the site links. Note the "v=" —
# an earlier "v15" (no equals) put 282 pages on a URL that a future bump,
# grepping for "?v=", would have skipped entirely.
CSS_V = "v=25"

# Deterministic waveform — identical on every rebuild, so pages stay diff-clean.
WAVEFORM = (
    '<svg class="wave" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true"><rect x="0.0" y="42.0" width="8" height="16" rx="4"/><rect x="15.6" y="35.0" width="8" height="30" rx="4"/><rect x="31.2" y="28.5" width="8" height="43" rx="4"/><rect x="46.8" y="24.0" width="8" height="52" rx="4"/><rect x="62.4" y="22.5" width="8" height="55" rx="4"/><rect x="78.0" y="24.0" width="8" height="52" rx="4"/><rect x="93.6" y="29.0" width="8" height="42" rx="4"/><rect x="109.2" y="36.5" width="8" height="27" rx="4"/><rect x="124.8" y="37.5" width="8" height="25" rx="4"/><rect x="140.4" y="31.0" width="8" height="38" rx="4"/><rect x="156.0" y="26.5" width="8" height="47" rx="4"/><rect x="171.6" y="25.5" width="8" height="49" rx="4"/><rect x="187.2" y="28.5" width="8" height="43" rx="4"/><rect x="202.8" y="30.0" width="8" height="40" rx="4"/><rect x="218.4" y="35.0" width="8" height="30" rx="4"/><rect x="234.0" y="41.5" width="8" height="17" rx="4"/><rect x="249.6" y="28.5" width="8" height="43" rx="4"/><rect x="265.2" y="17.5" width="8" height="65" rx="4"/><rect x="280.8" y="9.5" width="8" height="81" rx="4"/><rect x="296.4" y="6.5" width="8" height="87" rx="4"/><rect x="312.0" y="9.0" width="8" height="82" rx="4"/><rect x="327.6" y="15.5" width="8" height="69" rx="4"/><rect x="343.2" y="26.0" width="8" height="48" rx="4"/><rect x="358.8" y="25.0" width="8" height="50" rx="4"/><rect x="374.4" y="15.0" width="8" height="70" rx="4"/><rect x="390.0" y="9.0" width="8" height="82" rx="4"/><rect x="405.6" y="7.0" width="8" height="86" rx="4"/><rect x="421.2" y="11.0" width="8" height="78" rx="4"/><rect x="436.8" y="20.5" width="8" height="59" rx="4"/><rect x="452.4" y="34.0" width="8" height="32" rx="4"/><rect x="468.0" y="47.0" width="8" height="6" rx="4"/><rect x="483.6" y="35.0" width="8" height="30" rx="4"/><rect x="499.2" y="22.0" width="8" height="56" rx="4"/><rect x="514.8" y="13.0" width="8" height="74" rx="4"/><rect x="530.4" y="9.0" width="8" height="82" rx="4"/><rect x="546.0" y="11.0" width="8" height="78" rx="4"/><rect x="561.6" y="17.5" width="8" height="65" rx="4"/><rect x="577.2" y="27.5" width="8" height="45" rx="4"/><rect x="592.8" y="24.0" width="8" height="52" rx="4"/><rect x="608.4" y="13.0" width="8" height="74" rx="4"/><rect x="624.0" y="5.5" width="8" height="89" rx="4"/><rect x="639.6" y="3.5" width="8" height="93" rx="4"/><rect x="655.2" y="7.0" width="8" height="86" rx="4"/><rect x="670.8" y="15.0" width="8" height="70" rx="4"/><rect x="686.4" y="27.0" width="8" height="46" rx="4"/><rect x="702.0" y="37.5" width="8" height="25" rx="4"/><rect x="717.6" y="30.0" width="8" height="40" rx="4"/><rect x="733.2" y="25.0" width="8" height="50" rx="4"/><rect x="748.8" y="23.5" width="8" height="53" rx="4"/><rect x="764.4" y="26.0" width="8" height="48" rx="4"/><rect x="780.0" y="27.5" width="8" height="45" rx="4"/><rect x="795.6" y="32.5" width="8" height="35" rx="4"/><rect x="811.2" y="39.5" width="8" height="21" rx="4"/><rect x="826.8" y="35.5" width="8" height="29" rx="4"/><rect x="842.4" y="26.5" width="8" height="47" rx="4"/><rect x="858.0" y="21.0" width="8" height="58" rx="4"/><rect x="873.6" y="19.0" width="8" height="62" rx="4"/><rect x="889.2" y="21.0" width="8" height="58" rx="4"/><rect x="904.8" y="26.0" width="8" height="48" rx="4"/><rect x="920.4" y="33.0" width="8" height="34" rx="4"/><rect x="936.0" y="39.0" width="8" height="22" rx="4"/><rect x="951.6" y="34.0" width="8" height="32" rx="4"/><rect x="967.2" y="31.0" width="8" height="38" rx="4"/><rect x="982.8" y="30.5" width="8" height="39" rx="4"/></svg>')


# Landscape underlays, varied by kind so 249 pages don't all look identical.
# Landscapes only — GW's rule is no fish-holding shots as band underlays.
HERO_IMG = {
    "archive":   ("band-bynoe-flats-drone", 1600, 1200),
    "podcast":   ("band-pricing-glass-river", 1600, 1066),
    "radio":     ("band-texture-flats", 1600, 1200),
    "interview": ("band-bynoe-creek-texture", 1600, 900),
    "video":     ("band-video-flats-drone", 1600, 1066),
}


def _hero(kind, prefix="../"):
    slug, w, h = HERO_IMG.get(kind, HERO_IMG["podcast"])
    return (f'<picture class="hero-bg">\n'
            f'    <source type="image/avif" srcset="{prefix}assets/img/{slug}-640.avif 640w, '
            f'{prefix}assets/img/{slug}-1000.avif 1000w, {prefix}assets/img/{slug}-1600.avif 1600w" sizes="100vw">\n'
            f'    <img src="{prefix}assets/img/{slug}-1600.jpg" srcset="{prefix}assets/img/{slug}-640.jpg 640w, '
            f'{prefix}assets/img/{slug}-1000.jpg 1000w, {prefix}assets/img/{slug}-1600.jpg 1600w" '
            f'sizes="100vw" width="{w}" height="{h}" alt="" fetchpriority="high" decoding="async">\n'
            f'  </picture>')


def _nav():
    return """<header class="site">
  <nav class="nav">
    <a href="../index.html"><img src="../assets/logo-white.png" alt="Barefoot Fishing Safaris"></a>
    <button class="nav-toggle" aria-label="Menu" aria-expanded="false" onclick="var u=document.getElementById('navmenu');u.classList.toggle('open');this.setAttribute('aria-expanded',u.classList.contains('open'))">&#9776;</button>
    <ul id="navmenu">
      <li><a href="../index.html">Home</a></li>
      <li><a href="../index.html#safaris">Safaris</a></li>
      <li><a href="../media.html">Media</a></li>
      <li><a href="../gallery.html">Gallery</a></li>
      <li><a href="../about-barefoot.html">About</a></li>
      <li><a href="../index.html#contact" class="btn btn-primary">Book a Trip</a></li>
    </ul>
  </nav>
</header>"""


def _footer():
    return """<footer class="site">
  <div class="wrap">
    <div class="foot-note">
      <span>&copy; <span class="copyyear">2026</span><script>document.currentScript.previousSibling.textContent=new Date().getFullYear()</script> Barefoot Fishing Safaris &middot; Coolalinga, Northern Territory &middot; <a href="../privacy-policy.html" style="color:inherit">Privacy</a> &middot; <a href="../booking-terms.html" style="color:inherit">Booking terms</a></span>
      <span>Fish with Watty &middot; 0417 272 871</span>
    </div>
  </div>
</footer>"""


def _hhmmss(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return None
    return f"PT{sec // 60}M{sec % 60}S"


def build_episode(ep, site_dir, neighbours=None):
    raw_path = ep["transcript"]
    paras, stats = clean(open(raw_path, encoding="utf-8").read())
    body = "\n      ".join(f"<p>{html.escape(p)}</p>" for p in paras)

    title = html.escape(ep["title"])
    show = html.escape(ep.get("show", ""))
    station = html.escape(ep.get("station", ""))
    date = ep["date"]
    # A manifest may supply dateLabel for items whose exact day is unknown
    # (e.g. an ABC file we can only place to the month).
    if ep.get("dateLabel"):
        nice_date = ep["dateLabel"]
    else:
        try:
            _d = datetime.date.fromisoformat(date)
            # Cross-platform day-without-leading-zero.
            nice_date = f"{_d.strftime('%A')} {_d.day} {_d.strftime('%B %Y')}"
        except ValueError:
            nice_date = date
    _sec = ep.get("dur")
    try:
        _sec = int(_sec)
        duration_label = f"{_sec // 60} min" if _sec >= 60 else f"{_sec} sec"
    except (TypeError, ValueError):
        duration_label = "Full segment"
    # Video channels are their own "show" and "station" — don't print it twice.
    eyebrow = show if show == station or not station else f"{show} &middot; {station}"
    hero_pic = _hero(ep.get("kind", "podcast"))

    # 249 pages that only link back to the index are a dead end for readers and
    # for crawlers. Offer the neighbouring episodes.
    if neighbours:
        cards = "\n".join(
            f'''      <a class="card sand epcard" href="{n["slug"]}.html">
        <div class="season">{html.escape(n.get("show",""))}</div>
        <h3>{html.escape(n["title"])}</h3>
        <span class="go">Listen &amp; read &rarr;</span>
      </a>''' for n in neighbours)
        more_block = f'''<section>
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">More from the archive</p>
      <h2>Keep listening</h2>
    </div>
    <div class="grid grid-3">
{cards}
    </div>
    <p class="epmeta" style="margin-top:2.4rem"><a href="../media.html#archive">The whole archive &rarr;</a> &nbsp;&middot;&nbsp; <a href="../media.html">Media Centre</a></p>
  </div>
</section>'''
    else:
        more_block = ('<section><div class="wrap"><p class="epmeta">'
                      '<a href="../media.html#archive">Back to the archive</a></p></div></section>')
    audio = html.escape(ep.get("audio", ""))
    listen = ep.get("page")

    if ep.get("kind") == "video":
        vid_id = ep["videoId"]
        schema = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": ep["title"],
            **({"uploadDate": date} if len(date) == 10 else {}),
            "description": f'{ep["title"]} — {ep.get("station", "")}',
            "inLanguage": "en-AU",
            "embedUrl": f"https://www.youtube-nocookie.com/embed/{vid_id}",
            "contentUrl": f"https://www.youtube.com/watch?v={vid_id}",
            "thumbnailUrl": f"https://i.ytimg.com/vi/{vid_id}/maxresdefault.jpg",
            "creator": {"@type": "Organization", "name": ep.get("station", "")},
            **({"duration": _hhmmss(ep.get("dur"))} if _hhmmss(ep.get("dur")) else {}),
            # Hand the spoken content to the crawler directly.
            "transcript": " ".join(paras),
        }
    else:
        schema = {
            "@context": "https://schema.org",
            "@type": "PodcastEpisode",
            "name": ep["title"],
            **({"datePublished": date} if len(date) == 10 else {}),
            "partOfSeries": {"@type": "PodcastSeries", "name": ep.get("show", "")},
            "inLanguage": "en-AU",
            "author": {"@type": "Person", "name": 'Glenn "Watty" Watt'},
            "publisher": {"@type": "Organization", "name": ep.get("station", "")},
            "associatedMedia": {
                "@type": "AudioObject",
                "contentUrl": ep.get("audio", ""),
                "encodingFormat": "audio/mpeg",
                **({"duration": _hhmmss(ep.get("dur"))} if _hhmmss(ep.get("dur")) else {}),
                "transcript": " ".join(paras),
            },
        }

    if ep.get("kind") == "video":
        vid = ep["videoId"]
        media_block = f'''<div class="vidcard vsolo">
      <div class="vthumb" data-yt="{vid}" role="button" tabindex="0" aria-label="Play video">
        <picture>
          <source type="image/avif" srcset="../assets/img/yt-{vid}-640.avif 640w, ../assets/img/yt-{vid}-1000.avif 1000w" sizes="(max-width:860px) 100vw, 820px">
          <img src="../assets/img/yt-{vid}-640.jpg" srcset="../assets/img/yt-{vid}-640.jpg 640w, ../assets/img/yt-{vid}-1000.jpg 1000w" sizes="(max-width:860px) 100vw, 820px" width="1280" height="720" alt="{title} — video still" loading="lazy" decoding="async">
        </picture>
        <span class="play"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg></span>
      </div>
    </div>'''
        # Click-to-play: the iframe is only created on click, so a page full of
        # transcript doesn't drag in YouTube on load. Keyboard-operable because
        # the thumb is a role=button, not a link.
        player_script = '''<script>
document.querySelectorAll('.vthumb[data-yt]').forEach(function(thumb){
  function play(){
    var id=thumb.getAttribute('data-yt'); if(!id||thumb.querySelector('iframe')) return;
    var h=document.querySelector('h1');
    var f=document.createElement('iframe');
    f.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0';
    f.title=h?h.textContent.trim():'Video';
    f.allow='accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
    f.setAttribute('allowfullscreen',''); thumb.innerHTML=''; thumb.appendChild(f);
  }
  thumb.addEventListener('click',play);
  thumb.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();play();}});
});
</script>
'''
    else:
        player_script = ""
        media_block = f'''<div class="player">
      <picture class="pbg">
        <source type="image/avif" srcset="../assets/img/band-texture-flats-1000.avif 1000w, ../assets/img/band-texture-flats-1600.avif 1600w" sizes="(max-width:860px) 100vw, 820px">
        <img src="../assets/img/band-texture-flats-1000.jpg" srcset="../assets/img/band-texture-flats-1000.jpg 1000w, ../assets/img/band-texture-flats-1600.jpg 1600w" sizes="(max-width:860px) 100vw, 820px" width="1600" height="1200" alt="" loading="lazy" decoding="async">
      </picture>
      <div class="pinner">
        <p class="plabel">Listen &middot; {duration_label}</p>
        {WAVEFORM}
        <audio controls preload="none" src="{audio}">Your browser can&rsquo;t play audio &mdash; <a href="{audio}">download the file</a>.</audio>
      </div>
    </div>'''

    listen_line = (
        f'<p class="tnote">Originally broadcast on {station}. '
        f'<a href="{html.escape(listen)}" target="_blank" rel="noopener">'
        f'{"Watch on" if ep.get("kind")=="video" else "Listen on the"} {show}</a>.</p>' if listen else
        f'<p class="tnote">Originally broadcast on {station}.</p>')

    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Barefoot Fishing Safaris</title>
<meta name="description" content="{title} &mdash; {show} on {station}, {date}. Full transcript and audio.">
<link rel="icon" type="image/png" href="../assets/fish-icon.png">
<link rel="stylesheet" href="../styles.css?{CSS_V}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
{head_meta("media/" + ep["slug"] + ".html", f"{title} &mdash; {show} on {station}, {date}. Full transcript and audio.", image=f"https://barefootfishingsafaris.com.au/assets/img/{HERO_IMG.get(ep.get('kind'), HERO_IMG['podcast'])[0]}-1600.jpg")}
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=1)}
</script>
</head>
<body>

{_nav()}

<section class="subhero photohero">
  {hero_pic}
  <div class="hero-content">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    <p class="hero-sub quiet">{nice_date}</p>
  </div>
</section>

<!-- Player and transcript live in one textured band — split across two
     sections the collapsed transcript left a near-empty stripe. -->
<section class="bandtexture soft">
  <picture class="band-bg">
    <source type="image/avif" srcset="../assets/img/band-texture-flats-1000.avif 1000w, ../assets/img/band-texture-flats-1600.avif 1600w" sizes="100vw">
    <img src="../assets/img/band-texture-flats-1600.jpg" sizes="100vw" width="1600" height="1200" alt="" loading="lazy" decoding="async">
  </picture>
  <div class="wrap">
    <div class="audiowrap">
    {media_block}
    {listen_line}
    </div>
    <div class="transcript">
      <details>
        <summary>Read the full transcript ({stats['words']:,} words)</summary>
        <div class="tbody">
        {body}
        </div>
      </details>
    </div>
  </div>
</section>

{more_block}

{_footer()}

{player_script}</body>
</html>
"""


def main():
    site_dir, feed = sys.argv[1], sys.argv[2]
    eps = json.load(open(feed, encoding="utf-8"))
    out_dir = os.path.join(site_dir, "media")
    os.makedirs(out_dir, exist_ok=True)
    usable = [e for e in eps if os.path.exists(e["transcript"])]
    for e in eps:
        if e not in usable:
            print(f"  skip (no transcript): {e['slug']}")

    # Neighbours: nearest episodes of the same kind, newest first.
    by_kind = {}
    for e in usable:
        by_kind.setdefault(e.get("kind", "podcast"), []).append(e)
    for v in by_kind.values():
        v.sort(key=lambda x: x["date"], reverse=True)

    built = []
    for ep in usable:
        sibs = by_kind[ep.get("kind", "podcast")]
        i = sibs.index(ep)
        near = [x for x in (sibs[i - 1:i] + sibs[i + 1:i + 3]) if x is not ep][:3]
        if len(near) < 3:  # top or bottom of a short list — pad from the same kind
            near += [x for x in sibs if x is not ep and x not in near][:3 - len(near)]
        path = os.path.join(out_dir, ep["slug"] + ".html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_episode(ep, site_dir, neighbours=near))
        built.append(ep["slug"])
    print(f"built {len(built)} episode pages -> {out_dir}")
    return built


if __name__ == "__main__":
    main()


def build_index(eps, site_dir):
    """The archive page. The premium items (video, interviews, ABC) get real
    cards — a text list made this read like a library catalogue. Only the 228
    dated Bag a Barra segments stay as lists, collapsed by year."""
    import collections
    radio = [e for e in eps if e.get("kind") == "radio"]
    pod = [e for e in eps if e.get("kind") == "podcast"]
    interviews = [e for e in eps if e.get("kind") == "interview"]
    videos = [e for e in eps if e.get("kind") == "video"]
    total = len(pod) + len(radio) + len(interviews) + len(videos)

    def vcard(e):
        v = e["videoId"]
        return f'''      <a class="vidcard" href="media/{e["slug"]}.html">
        <div class="vthumb">
          <picture>
            <source type="image/avif" srcset="assets/img/yt-{v}-640.avif 640w, assets/img/yt-{v}-1000.avif 1000w" sizes="(max-width:560px) 100vw, (max-width:860px) 50vw, 33vw">
            <img src="assets/img/yt-{v}-640.jpg" srcset="assets/img/yt-{v}-640.jpg 640w, assets/img/yt-{v}-1000.jpg 1000w" sizes="(max-width:560px) 100vw, (max-width:860px) 50vw, 33vw" width="1280" height="720" alt="" loading="lazy" decoding="async">
          </picture>
        </div>
        <div class="vbody">
          <span class="vchan">{html.escape(e.get("station",""))}</span>
          <h3>{html.escape(e["title"])}</h3>
          <span class="go">Watch &amp; read &rarr;</span>
        </div>
      </a>'''

    def scard(e, sub):
        return f'''      <a class="card sand epcard" href="media/{e["slug"]}.html">
        <div class="season">{html.escape(sub)}</div>
        <h3>{html.escape(e["title"])}</h3>
        <span class="go">Listen &amp; read &rarr;</span>
      </a>'''

    vids_html = "\n".join(vcard(e) for e in sorted(videos, key=lambda x: x["date"], reverse=True))
    iv_html = "\n".join(scard(e, e.get("station","")) for e in sorted(interviews, key=lambda x: x["date"], reverse=True))
    abc_html = "\n".join(scard(e, e.get("dateLabel") or e["title"].split("— ",1)[-1])
                         for e in sorted(radio, key=lambda x: x["date"], reverse=True))

    by_year = collections.defaultdict(list)
    for e in pod:
        by_year[e["date"][:4]].append(e)
    years, newest = [], (max(by_year) if by_year else None)
    for y in sorted(by_year, reverse=True):
        items = "\n          ".join(
            f'<li><a href="media/{e["slug"]}.html">{html.escape(e["title"].split("— ",1)[-1])}</a></li>'
            for e in sorted(by_year[y], key=lambda x: x["date"], reverse=True))
        years.append(f'''      <details class="yr"{" open" if y == newest else ""}>
        <summary>{y} <span class="cnt">{len(by_year[y])} segments</span></summary>
        <ul class="eplist">
          {items}
        </ul>
      </details>''')
    years_html = "\n".join(years)

    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radio, Podcast &amp; Video Archive &mdash; Every Appearance, Transcribed | Barefoot Fishing Safaris</title>
<meta name="description" content="Every radio segment, podcast and video appearance by Glenn &quot;Watty&quot; Watt &mdash; {total} of them going back to 2019, each with audio and a full transcript.">
<link rel="icon" type="image/png" href="assets/fish-icon.png">
<link rel="stylesheet" href="styles.css?{CSS_V}">
<link rel="preload" as="image" type="image/avif" imagesrcset="assets/img/band-bynoe-flats-drone-640.avif 640w, assets/img/band-bynoe-flats-drone-1000.avif 1000w, assets/img/band-bynoe-flats-drone-1600.avif 1600w" imagesizes="100vw">
<meta property="og:type" content="website">
<meta property="og:title" content="Seven years of barra talk — the Barefoot archive">
{head_meta("media.html", f"Every radio segment, podcast and video appearance by Glenn &quot;Watty&quot; Watt &mdash; {total} of them going back to 2019, each with audio and a full transcript.")}
<script type="application/ld+json">
{{
 "@context":"https://schema.org",
 "@type":"CollectionPage",
 "name":"Barefoot radio, podcast & video archive",
 "description":"Every radio segment, podcast and video appearance by Glenn \"Watty\" Watt, with audio and full transcripts.",
 "inLanguage":"en-AU",
 "publisher":{{"@type":"Organization","name":"Barefoot Fishing Safaris"}}
}}
</script>
</head>
<body>

{_nav().replace('../', '')}

<section class="subhero photohero tall">
  {_hero("archive", prefix="")}
  <div class="hero-content">
    <p class="eyebrow">The archive</p>
    <div class="hero-titlerow">
      <svg class="hero-fish" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12c2.5-4 8-6 13-3.5 2.2 1.1 3.5 2.3 3.5 3.5s-1.3 2.4-3.5 3.5C11 18 5.5 16 3 12z"/><path d="M19.5 12L23 8v8z"/><circle cx="7" cy="10.8" r=".7"/></svg>
      <h1>Seven years of barra talk</h1>
    </div>
    <p class="hero-sub quiet">Every radio segment, podcast and video appearance &mdash; transcribed in full.</p>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">On camera</p>
      <h2>Video appearances</h2>
      <p>Filmed by the people who were there. Every one has the full conversation written out underneath it.</p>
    </div>
    <div class="vidgrid">
{vids_html}
    </div>
  </div>
</section>

<section class="cream">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">Sat down properly</p>
      <h2>Long-form interviews</h2>
    </div>
    <div class="grid grid-3">
{iv_html}
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">ABC Radio Darwin</p>
      <h2>Fishing on Arvos</h2>
      <p>Wednesday afternoons with Liz Trevaskis and Rocky Edwards.</p>
    </div>
    <div class="grid grid-3">
{abc_html}
    </div>
  </div>
</section>

<section class="cream">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">Every Friday, for years</p>
      <h2>Bag a Barra &mdash; {len(pod)} segments</h2>
      <p>Watty&rsquo;s weekly spot on Oz Off Road Radio. Pick a year.</p>
    </div>
{years_html}
    <p class="epmeta" style="margin-top:2.4rem"><a href="media.html">&larr; Back to the Media Centre</a></p>
  </div>
</section>

{_footer().replace('../', '')}

</body>
</html>
"""
