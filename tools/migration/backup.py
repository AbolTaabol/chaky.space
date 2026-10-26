"""Snapshot the in-scope chaky.space pages and every Super-hosted media file they use.

Usage: python backup.py <scope.json> <out_dir>
Writes <out_dir>/super-snapshot/*.html, <out_dir>/media/*, <out_dir>/manifest.json
"""
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import urllib.request

SITE = "https://chaky.space"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit Chrome/130 Safari"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
       "image/svg+xml": ".svg", "video/mp4": ".mp4", "video/quicktime": ".mov",
       "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico", "image/avif": ".avif"}

scope = json.load(open(sys.argv[1]))
out = sys.argv[2]
os.makedirs(f"{out}/super-snapshot", exist_ok=True)
os.makedirs(f"{out}/media", exist_ok=True)


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)


def page_file(p):
    return "index" if p == "/" else p.strip("/").replace("/", "__")


# 1. pages
pages = {}
for p in scope:
    t = fetch(SITE + p).read().decode("utf8")
    pages[p] = t
    open(f"{out}/super-snapshot/{page_file(p)}.html", "w").write(t)
print("pages saved:", len(pages))

# 2. collect media keys -> original URL
spr = re.compile(r"https://images\.spr\.so/cdn-cgi/imagedelivery/([^/\"']+)/([0-9a-f-]{36})/([^/\"']+)/")
assets = re.compile(r"https://assets(?:-v2)?\.super\.so/c1000a90-84bb-44d4-9fe4-6222c9dc6212/"
                    r"(images|videos|uploads)/[^\"'\s)\\]+")
media = {}  # key -> url
for t in pages.values():
    t = html.unescape(t)
    for acct, uid, name in spr.findall(t):
        media[uid] = f"https://images.spr.so/cdn-cgi/imagedelivery/{acct}/{uid}/{name}/public"
    for m in assets.finditer(t):
        url = m.group(0).rstrip("\\")
        key = url.split("/c1000a90-84bb-44d4-9fe4-6222c9dc6212/")[1].replace("/", "__")
        media[key] = url
print("media files:", len(media))


def dl(item):
    key, url = item
    try:
        done = [f for f in os.listdir(f"{out}/media") if os.path.splitext(f)[0] == re.sub(r"\.[a-z0-9]{2,4}$", "", key)]
        if done:
            f = done[0]
            return key, {"url": url, "file": f, "type": "", "bytes": os.path.getsize(f"{out}/media/{f}")}
        r = fetch(url)
        data = r.read()
        ctype = r.headers.get("Content-Type", "").split(";")[0]
        base = re.sub(r"\.[a-z0-9]{2,4}$", "", key)
        name = base + EXT.get(ctype, os.path.splitext(key)[1] or ".bin")
        open(f"{out}/media/{name}", "wb").write(data)
        return key, {"url": url, "file": name, "type": ctype, "bytes": len(data)}
    except Exception as e:  # keep going, report at the end
        return key, {"url": url, "error": str(e)}


with cf.ThreadPoolExecutor(8) as ex:
    manifest = dict(ex.map(dl, sorted(media.items())))

json.dump(manifest, open(f"{out}/manifest.json", "w"), indent=1)
errs = {k: v for k, v in manifest.items() if "error" in v}
total = sum(v.get("bytes", 0) for v in manifest.values())
print(f"downloaded {len(manifest) - len(errs)} files, {total / 1e6:.1f} MB, errors: {len(errs)}")
for k, v in errs.items():
    print("  ERR", k, v["error"])
