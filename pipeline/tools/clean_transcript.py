"""
Turn raw on-device transcriber output into publishable prose.

Three jobs:
  1. Find where Watty's segment actually starts and stops. Episodes are topped
     and tailed with network ads that change every year — News 24, Shopify,
     an NRL podcast, Crime Central, drive.com.au, radio-industry house ads.
     A blacklist of advertiser names can never keep up, so instead we locate
     the segment by CONTENT: ads contain no fishing vocabulary, the segment is
     saturated with it. Anything outside that window is somebody else's copy
     and is not ours to republish.
  2. Fix the proper nouns the recogniser reliably mishears.
  3. Group one-sentence-per-line output into readable paragraphs.

Used by build_media.py. Safe to re-run — it works off the raw .txt every time,
so a correction here reflows through every generated page on the next build.
"""
import re

# Left side is what the recogniser actually hears. Measured on real episodes.
# NOTE: "Captain Watty" is correct — it's Watty's on-air name in the NT.
GLOSSARY = [
    (r"\bbag ?a ?barrow\b", "Bag a Barra"), (r"\bbag of barrow\b", "Bag a Barra"),
    (r"\bbagga barra\b", "Bag a Barra"), (r"\bbag of barra\b", "Bag a Barra"),
    (r"\bbag a barra\b", "Bag a Barra"),
    (r"\bWaddy\b", "Watty"), (r"\bWattie\b", "Watty"),
    (r"\bGlenn Watts\b", "Glenn Watt"), (r"\bGlen Watt\b", "Glenn Watt"),
    (r"\buni ?dan\b", "Uniden"), (r"\bunigen\b", "uniden"),
    (r"\btop bin\b", "Top End"), (r"\btop end\b", "Top End"),
    (r"\bbarefoot fishing safaris?\b", "Barefoot Fishing Safaris"),
    (r"\bbarefoot\b", "Barefoot"),
    (r"\bbynoe\b", "Bynoe"), (r"\bby no harbour\b", "Bynoe Harbour"),
    (r"\bkakadu\b", "Kakadu"), (r"\bdaly river\b", "Daly River"),
    (r"\bshady camp\b", "Shady Camp"), (r"\bcorroboree\b", "Corroboree"),
    (r"\bdundee\b", "Dundee"), (r"\bdarwin\b", "Darwin"),
    (r"\bafant\b", "AFANT"), (r"\ba ?fant\b", "AFANT"),
    # "AFANT" reliably comes out as "Afghan" before these nouns. Scoped tightly
    # on purpose — a bare Afghan->AFANT rule would corrupt unrelated sentences.
    (r"\bAfghan (constituents|members|reps|representatives)\b", r"AFANT \1"),
    # "barra fishing" reliably comes out as "bar/barrel efficient".
    (r"\b(bar|barrel|barra)\s+efficient\b", "barra fishing"),
    (r"\beaster alligator\b", "East Alligator"),
    (r"\beast alligator\b", "East Alligator"),
    # "barra" comes out as "baron" about twenty times across the archive.
    # Guarded: "you've become a land baron up there" is a real sentence, and
    # a bare rule would have mangled it.
    (r"(?<!land )\bbarons\b", "barra"), (r"(?<!land )\bbaron\b", "barra"),

    # PLACE NAMES. GW's rule (17 Aug 2026): a wrong place name is a reputation
    # killer — locals spot it instantly. The transcriber mangles them badly, so
    # these run over the whole archive. Verified list: articles/placenames.txt.
    (r"\bbino harvey\b", "Bynoe Harbour"),
    (r"\bbino harbour\b", "Bynoe Harbour"), (r"\bbino\b", "Bynoe"),
    (r"\bkokatoo\b", "Kakadu"), (r"\bkokadu\b", "Kakadu"),
    (r"\barnamland\b", "Arnhem Land"), (r"\barnam land\b", "Arnhem Land"),
    (r"\bshaw bay\b", "Shoal Bay"), (r"\bshore bay\b", "Shoal Bay"),
    (r"\bmganella\b", "Murgenella"),
    # "Daly" comes out as "daily". Scoped so "on a daily basis" survives.
    # "Daily Rivers" is the transcriber hearing "Daly River's" — the trailing "s"
    # defeated the \b in the singular rule, so four pages kept a wrong place name
    # long after the archive-wide fix. Plural rule goes FIRST or it never fires.
    (r"\bdaily rivers\b", "Daly River's"),
    (r"\bdaily river\b", "Daly River"), (r"\bdaily waters\b", "Daly Waters"),
    (r"\bthe daily\b(?!\s+(?:basis|routine|rate|grind|life|news|paper|dose|special))",
     "the Daly"),
    (r"\bunidad\b", "Uniden"),
    (r"\bdarramundi\b", "barramundi"), (r"\bkokatoo\b", "Kakadu"),

    # --- Added 5 Oct 2026, from the Sep 2026 batch. Counts are hits across
    # the 253-episode raw archive at time of writing.
    # "Corroboree" comes out as the English verb "corroborate" — 102 times in
    # 53 episodes, and on inspection not ONE was the real verb ("corroborate
    # Billabong", "corroborate tavern", "corroborate is"). Guarded anyway: the
    # lookahead leaves a genuine transitive "corroborate the story" alone.
    # Inflected forms (corroborated/-es/-ing) never match — \b sees to that.
    # Guard is deliberately narrow. A determiner alone is NOT a tell — "at a
    # Corroboree the other day", "done Corroboree a couple of times", "on
    # Corroboree this morning" are all the place, and a determiner-wide
    # lookahead silently left five pages wrong. Only the abstract objects the
    # real verb actually takes are excluded.
    (r"\bcorroborates?\b(?!\s+(?:the|that|this|his|her|their|our|my|your|its|a|an)?\s*"
     r"(?:story|stories|account|accounts|claim|claims|evidence|version|versions|"
     r"testimony|report|reports|finding|findings|statement|statements|allegation|"
     r"allegations|theory|suspicion|suspicions|detail|details|fact|facts)\b)",
     "Corroboree"),
    (r"\bkakadoo\b", "Kakadu"),                 # 25 hits, 21 episodes
    (r"\bwillabong\b", "billabong"),            # 3 hits
    # Noonamah (Stuart Hwy, south of Darwin — the rodeo and the tavern).
    # 15 hits across 10 episodes, spelled three different ways.
    # The recogniser also runs "Noonamah Rodeo" together into one token
    # ("Nunamaradeo"), which is why a plain \bnunamar\b rule missed four pages.
    # Merged forms must come first.
    (r"\bnunamar[ai]deos\b", "Noonamah Rodeos"),
    (r"\bnunamar[ai]deo\b", "Noonamah Rodeo"),
    (r"\bnunamar\b", "Noonamah"), (r"\bnunuma\b", "Noonamah"),
    (r"\bnooney\b", "Noonamah"),
    (r"\bhumpty[\s-]*(?:doo|dee|do)\b", "Humpty Doo"),   # 26 hits, 15 episodes
    (r"\bcrabclaw\b", "Crab Claw"), (r"\bcrab ?call\b", "Crab Claw"),
    (r"\bmental beach\b", "Mindil Beach"),
    (r"\bcallum bay\b", "Cullen Bay"), (r"\bcolum bay\b", "Cullen Bay"),
    (r"\bcasarena\b", "Casuarina"),
    (r"\bmug crabs\b", "mud crabs"), (r"\bmug crab\b", "mud crab"),
    (r"\brefishing\b", "reef fishing"),         # 4 hits — "a bit of reef fishing"
    # "barra" also comes out as "barrel". UNGUARDED THIS WOULD BE WRONG: one
    # episode has "we got about half a barrel there with the taps still on",
    # which is a beer barrel and must survive. So only the fishing verbs.
    (r"\b(catch|caught|catching|flick up|flicked up|hook|hooked|land|landed|got)"
     r"\s+a\s+barrel\b", r"\1 a barra"),
    (r"\bbarrel fillet\b", "barra fillet"),

    # --- Added 30-31 Oct 2026 on the Mac (Bag a Barra 30 Oct publish and the
    # "glossary fixes (trevally, Noonamah)" commit). The Drive backup of this
    # file pre-dated them; recovered on 12 Nov 2026 from the word changes in
    # those commits and proven by rebuilding four Bag a Barra pages byte-for-
    # byte identical to the live ones. Must sit AFTER the "bag a barrow" rules.
    (r"\bbuino harvest\b", "Bynoe Harbour"), (r"\bbuino\b", "Bynoe"),
    (r"\bcrabcore\b", "Crab Claw"),
    (r"\bmangrave\b", "mangrove"),
    (r"\bWadi\b", "Watty"),
    (r"\bbarrows\b", "barra"), (r"\bbarrow\b", "barra"),
    (r"\btrevellis\b", "trevally"), (r"\btrevelli\b", "trevally"),
    (r"\bnuneham\b", "Noonamah"),
]

# The segment's own top-of-show sting. When present it's the most reliable
# start point there is, so it wins over the vocabulary heuristic.
START_MARKER = re.compile(
    r"time to head to the Top End|bag ?a ?barr|bag of barr|bagga barra|"
    r"camping and off.?road radio show|Barefoot Fishing Safaris", re.I)

# Vocabulary that appears constantly in the segment and essentially never in a
# network ad read. Used to find the last line of real content.
FISHY = re.compile(
    r"\bbarr[ao]|\bfish|\btide|\bboat|\briver|\bcreek|\blure|\bcast\b|\bcatch|"
    r"\breel\b|\bcroc|\brun.?off|\bharbour|\bbait|\bangler|\bjack\b|\bthreadfin|"
    r"\bsaratoga|\bmackerel|\bsnapper|\bramp\b|\btinnie|\bwet season|\bdry season|"
    r"\bmangrove|\bbillabong|\bflats\b|\bsalt ?water|\bfresh ?water", re.I)

# Belt and braces for ad copy that lands *inside* the window.
HARD_JUNK = re.compile(
    r"omnystudio|omny studio|see omnystudio|privacy information|"
    r"subscribe button|hit the subscribe|download the .{0,30}app|"
    r"drive\.com\.au|shopify\.com|cra\.au|podcast advertising", re.I)

# The sung station jingle — the recogniser turns singing into pure noise.
JINGLE = re.compile(r"nitty,? ?nitty|welcome fish|little rat,? ?book|"
                    r"rat booker|she's a? tumacho|i'll search, that show", re.I)


def _fix(text: str) -> str:
    for pat, rep in GLOSSARY:
        text = re.sub(pat, rep, text, flags=re.I)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def _window(lines):
    """Index range of Watty's actual segment, excluding the ad reads."""
    fishy = [i for i, l in enumerate(lines) if FISHY.search(l)]
    if not fishy:
        return 0, len(lines) - 1
    start_hits = [i for i, l in enumerate(lines) if START_MARKER.search(l)]
    # Prefer the sting, but only if it sits at or before the content.
    start = next((i for i in start_hits if i <= fishy[-1]), fishy[0])
    return min(start, fishy[0]) if start_hits else fishy[0], fishy[-1]


def clean(raw: str, para_sentences: int = 4):
    """Returns (paragraphs, stats). Trims ads, fixes names, groups prose."""
    lines = [l.strip() for l in raw.splitlines()]
    lines = [l for l in lines if l and not JINGLE.search(l)]
    if not lines:
        return [], {"trimmed": 0, "words": 0, "paras": 0}

    lo, hi = _window(lines)
    body = lines[lo:hi + 1]
    trimmed = len(lines) - len(body)

    kept = [_fix(l) for l in body if not HARD_JUNK.search(l)]
    trimmed += len(body) - len(kept)

    paras = [" ".join(kept[i:i + para_sentences])
             for i in range(0, len(kept), para_sentences)]
    words = sum(len(p.split()) for p in paras)
    return paras, {"trimmed": trimmed, "words": words, "paras": len(paras)}
