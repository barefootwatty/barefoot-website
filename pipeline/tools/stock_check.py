#!/usr/bin/env python3
"""Stock link check: can the live Walkabout shop read shirt and shorts stock from the Google Sheet?

Runs on GitHub's servers every 30 minutes (.github/workflows/stock-check.yml).
Silent when all is well. If the shop cannot read the Sheet it fails, and GitHub
emails the repo owner. It emails again every 30 minutes until the link is fixed.

While the link is broken, buyers see "(checking stock)" on shirts, shorts and
Expedition Kits and cannot order them. Rods keep selling. Nothing is oversold.

Run it by hand from the repo root:   python3 pipeline/tools/stock_check.py
"""
import json
import os
import sys
import time
import urllib.request

URL = os.environ.get("STOCK_CHECK_URL", "https://barefootfishingsafaris.com.au/api/walkabout-checkout?stock=check")
TRIES = int(os.environ.get("STOCK_CHECK_TRIES", "4"))    # a blip at Google must not raise an alarm,
WAIT = float(os.environ.get("STOCK_CHECK_WAIT", "45"))   # so it looks a few times, 45 seconds apart

# What each fault code from the shop means, and what puts it right. Plain words on purpose.
WHY = {
    "sheet-tab-not-found": (
        "A tab on the Barefoot Merch Manifest has been renamed or deleted.",
        "Name the tabs exactly Stock and Orders again."),
    "stock-tab-headings": (
        "On the Stock tab, the heading SKU or Available has been renamed, or Available has been moved away from the SKU columns.",
        "Put the headings SKU and Available back in row 1 of the Stock tab, in the same block of columns."),
    "stock-tab-lines": (
        "None of the SKU codes on the Stock tab match the ones the website sells (they start BFS-CLS-, BFS-HLS-, BFS-FS-).",
        "Put the SKU codes back in the SKU column of the Stock tab."),
    "orders-tab-headings": (
        "On the Orders tab, Order ref is no longer in column A, or Status is no longer in column K.",
        "Move the columns back: Order ref in column A, Status in column K, headings in row 1."),
    "sheet-not-shared-with-the-reader": (
        "The Barefoot Merch Manifest is no longer shared with the website's Google reader account.",
        "Ask Claude to share the Sheet with the website's reader again (Viewer is enough)."),
    "google-too-slow": (
        "Google took too long to answer, several times in a row.",
        "Usually nothing: it clears by itself. If these emails keep coming for more than an hour, ask Claude to look."),
    "google-unreachable": (
        "Google could not be reached, several times in a row.",
        "Usually nothing: it clears by itself. If these emails keep coming for more than an hour, ask Claude to look."),
    "shop-not-answering": (
        "The shop's own stock check did not answer properly. The Walkabout checkout itself may be down.",
        "Open the Walkabout page and try adding a rod. If that fails too, ask Claude to look straight away."),
}
SETTINGS = (
    "The link between the website (Vercel) and Google has stopped working. A setting has been changed or removed.",
    "Ask Claude to check the stock settings in Vercel and the Google project. The shop's header comment lists them.")


def look():
    """One look at the shop. Returns (healthy, fault code, Stock tab lines it could not read, where stock is coming from or why there was no answer)."""
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "barefoot-stock-check", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
        if not isinstance(d, dict) or "from" not in d:
            return False, "shop-not-answering", [], "the answer was not the stock check's"
    except Exception as e:  # no answer, an error page, or not JSON
        return False, "shop-not-answering", [], str(e)[:200]
    missing = [str(m) for m in (d.get("missing") or [])]
    if d.get("from") == "sheet" and not missing:
        return True, "", [], ""
    if d.get("from") == "sheet":
        return False, "lines-missing", missing, ""
    return False, str(d.get("problem") or "shop-not-answering"), missing, "stock is coming from: %s" % d.get("from")


def main():
    code, missing, detail = "", [], ""
    for attempt in range(1, TRIES + 1):
        healthy, code, missing, detail = look()
        if healthy:
            print("OK: the Walkabout shop is reading shirt and shorts stock from the Sheet (look %d of %d)." % (attempt, TRIES))
            return 0
        print("Look %d of %d: not healthy (%s). %s" % (attempt, TRIES, code, detail))
        if attempt < TRIES:
            time.sleep(WAIT)

    if code == "lines-missing":
        title = "THE WALKABOUT SHOP CANNOT READ SOME LINES OF THE STOCK TAB"
        seen = "These sizes show as SOLD OUT on the website until it is fixed: %s. Everything else is selling normally." % ", ".join(missing)
        why = "Those SKU lines are missing from the Stock tab, or their Available cell is not a plain number (an error or text)."
        fix = "Put the SKU code back on its line, or fix the Available cell so it shows a number."
    else:
        title = "THE WALKABOUT SHOP CANNOT READ THE STOCK SHEET"
        seen = ('Shirts, shorts and Expedition Kits say "(checking stock)" and cannot be ordered. '
                "Rods still sell. Nothing is oversold.")
        if code == "shop-not-answering":
            title = "THE WALKABOUT SHOP'S STOCK CHECK IS NOT ANSWERING"
            seen = "Not known: the shop did not answer. The whole Walkabout order box may be out of action."
        elif detail.endswith(": saved"):
            seen = ("Nothing yet: the shop is still selling from its last good reading of the Sheet. If this goes on for "
                    '30 minutes, shirts, shorts and Expedition Kits will say "(checking stock)". Rods are not affected.')
        if code.startswith("sheet-5") or code == "sheet-429":
            why, fix = WHY["google-unreachable"]
        else:
            why, fix = WHY.get(code, SETTINGS)
    lines = [
        title,
        "",
        "What buyers see:  " + seen,
        "Why:              %s (fault code: %s)" % (why, code),
        "What to do:       " + fix,
        "",
        "This check runs every 30 minutes and emails again until the shop can read the Sheet.",
        "Checked: " + URL,
    ]
    print("\n" + "\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## %s\n\n" % title + "\n".join("- " + l for l in lines[2:5]) + "\n\n" + lines[6] + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
