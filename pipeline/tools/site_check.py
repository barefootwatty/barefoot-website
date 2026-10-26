#!/usr/bin/env python3
"""
Weekly health check for barefootfishingsafaris.com.au, run by GitHub Actions
(no Mac involved). Exits 1, which makes GitHub email the repo owner, if:

  * any page in sitemap.xml does not return 200
  * any old-website URL in pipeline/legacy-paths.txt no longer lands on a live page
  * the enquiry form endpoint is down (5xx) or missing
  * the security certificate has under 10 days left (it should renew itself
    around 30 days out, so this means the renewal failed)
  * the www address, or the two holding domains, stop answering

Silent when everything is fine.
"""
import concurrent.futures as cf
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://barefootfishingsafaris.com.au"
HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(HERE, "..", "legacy-paths.txt")
UA = {"User-Agent": "barefoot-site-check/1.0"}
problems = []


class Follow308(urllib.request.HTTPRedirectHandler):
    """Older Pythons stop at a 308; Vercel's permanent redirects are 308s."""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, 307, msg, headers)


OPENER = urllib.request.build_opener(Follow308)


def get(url, method="GET", data=None, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=UA)
            with OPENER.open(req, timeout=25) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            last = (e.code, url)
            if e.code < 500:
                return last
        except Exception as e:  # network blip
            last = (f"ERR {type(e).__name__}", url)
        time.sleep(2 * (i + 1))
    return last


def many(urls):
    with cf.ThreadPoolExecutor(8) as ex:
        return list(zip(urls, ex.map(lambda u: get(u), urls)))


# 1. every sitemap page is live
status, _ = get(BASE + "/sitemap.xml")
if status != 200:
    problems.append(f"sitemap.xml returned {status}")
    locs = []
else:
    xml = OPENER.open(urllib.request.Request(BASE + "/sitemap.xml", headers=UA), timeout=25).read().decode()
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
bad = [(u, r[0]) for u, r in many(locs) if r[0] != 200]
for u, s in bad[:25]:
    problems.append(f"page down: {u} -> {s}")
if len(bad) > 25:
    problems.append(f"...and {len(bad) - 25} more pages down")

# 2. old website links still land somewhere real
if os.path.exists(LEGACY):
    paths = [l.strip() for l in open(LEGACY) if l.strip() and not l.startswith("#")]
    dead = [(p, r[0]) for p, r in many([BASE + p for p in paths]) if r[0] != 200]
    for p, s in dead[:25]:
        problems.append(f"old link dead: {p.replace(BASE, '')} -> {s}")
    if len(dead) > 25:
        problems.append(f"...and {len(dead) - 25} more old links dead")

# 3. enquiry form endpoint: an empty POST must be refused politely (4xx), not crash (5xx)
s, _ = get(BASE + "/api/enquiry", method="POST", data=b"{}")
if not (isinstance(s, int) and 400 <= s < 500):
    problems.append(f"enquiry form endpoint answered {s} (expected a 4xx refusal)")

# 4. certificate
ctx = ssl.create_default_context()
with socket.create_connection(("barefootfishingsafaris.com.au", 443), timeout=15) as sock:
    with ctx.wrap_socket(sock, server_hostname="barefootfishingsafaris.com.au") as ss:
        exp = datetime.strptime(ss.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
days = (exp - datetime.now(timezone.utc)).days
if days < 10:
    problems.append(f"security certificate expires in {days} days and has not renewed")

# 5. the other addresses
for url in ("https://www.barefootfishingsafaris.com.au/", "https://barefootoutdoors.com.au/",
            "https://barefootconsulting.com.au/"):
    s, _ = get(url)
    if s != 200:
        problems.append(f"{url} -> {s}")

if problems:
    print("PROBLEMS FOUND:")
    print("\n".join(" - " + p for p in problems))
    sys.exit(1)
print(f"all good: {len(locs)} pages, old links, form, certificate ({days} days left)")
