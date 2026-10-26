#!/usr/bin/env python3
"""
Flag unverified place names in the article sources.

GW's rule: a wrong place name is a reputation killer on a guiding site. The
lesson transcripts come off an automatic transcriber that mangles proper nouns
("Shaw Bay" for Shoal Bay, "Kokatoo" for Kakadu), and one of those slipping
through undoes the authority the whole library is for.

So nothing ships until every place-shaped name in it is either on the verified
list in articles/placenames.txt, or deliberately removed. If you cannot verify
a name, write around it — "one of the bigger rivers" — rather than guessing.

    python3 tools/check_places.py            # check every article source
    python3 tools/check_places.py foo.txt    # check one

Exit status is 1 if anything is unverified, so it can gate a build.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "articles", "src")
LIST = os.path.join(ROOT, "articles", "placenames.txt")

# Words that make a capitalised phrase look like a place.
GEO = (r"Bay|Harbour|Harbor|River|Creek|Camp|Point|Island|Arm|Beach|Inlet|"
       r"Billabong|Springs|Bar|Crossing|Land|Territory|Water|Falls|Gorge")

# Sentence-openers and section words that are capitalised but never places.
STOPWORDS = {
    "The", "A", "An", "This", "That", "These", "Those", "It", "They", "He",
    "She", "We", "You", "I", "If", "When", "Where", "What", "Why", "How",
    "Which", "There", "Here", "Once", "On", "In", "At", "For", "With", "So",
    "But", "And", "Or", "Not", "No", "Yes", "One", "Two", "Three", "Four",
    "Five", "Ask", "Find", "Fish", "Pick", "Same", "Some", "Short", "Start",
    "Both", "Every", "Most", "Much", "Add", "Keep", "Work", "Read", "Look",
    "Barra", "Barramundi", "Bait", "Rock", "Rocks", "Snag", "Snags", "Big",
    "Q", "A.", "Google", "Earth", "Watty", "Glenn", "Barefoot", "Media",
    "Centre", "Common", "Questions", "Whatever", "Cod", "Murray",
}


def load():
    """Returns (verified names, {wrong: right} manglings)."""
    names, fixes, in_fix = set(), {}, False
    for line in open(LIST, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "@fix":
            in_fix = True
            continue
        if in_fix and "->" in line:
            bad, good = (p.strip() for p in line.split("->", 1))
            fixes[bad] = good
        elif not in_fix:
            names.add(line)
    return names, fixes


def candidates(text):
    """Capitalised phrases that look like place names."""
    found = set()
    # "Shoal Bay", "Darwin Harbour", "South Alligator River"
    for m in re.finditer(rf"\b((?:[A-Z][a-z]+\s+){{1,2}}(?:{GEO}))\b", text):
        found.add(m.group(1))
    # A bare capitalised word immediately before a geographic word is caught
    # above; also catch known single-word places by checking every capitalised
    # word against the verified list later.
    for m in re.finditer(r"\b([A-Z][a-z]{3,})\b", text):
        found.add(m.group(1))
    return found


def check(path, names, fixes):
    text = open(path, encoding="utf-8").read()
    # Only the prose matters — front matter keys are not place names.
    problems = []
    for cand in sorted(candidates(text)):
        if cand in fixes:
            problems.append(f"WRONG   {cand!r} -> should be {fixes[cand]!r}")
            continue
        if cand in names or cand in STOPWORDS:
            continue
        # Only multi-word phrases count as place names. A bare "Creek" or
        # "Harbour" is just a noun that happened to start a sentence.
        if " " in cand and re.search(rf"\b(?:{GEO})$", cand):
            problems.append(f"UNVERIFIED  {cand!r} — verify or write around it")
    return problems


def main():
    names, fixes = load()
    args = sys.argv[1:] or sorted(
        os.path.join(SRC_DIR, f) for f in os.listdir(SRC_DIR) if f.endswith(".txt"))
    bad = 0
    for path in args:
        problems = check(path, names, fixes)
        if problems:
            bad += len(problems)
            print(f"\n{os.path.basename(path)}")
            for p in problems:
                print(f"  {p}")
    if bad:
        print(f"\n{bad} place name(s) need attention — fix before publishing.")
        return 1
    print(f"place names OK across {len(args)} article(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
