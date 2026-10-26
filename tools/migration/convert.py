"""Convert the Super/Notion HTML snapshot of chaky.space into Markdown pages.

Usage: python convert.py <repo_dir>
Reads  <repo>/archive/super-snapshot/*.html, <repo>/archive/manifest.json, <repo>/archive/media/
Writes <repo>/src/content/pages/<path>/index.md (+ images), <repo>/public/media/<path>/*.mp4,
       <repo>/archive/conversion-report.json
"""
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, Tag

REPO = sys.argv[1]
SNAP = f"{REPO}/archive/super-snapshot"
MEDIA = f"{REPO}/archive/media"
PAGES = f"{REPO}/src/content/pages"
PUBLIC = f"{REPO}/public/media"
manifest = json.load(open(f"{REPO}/archive/manifest.json"))

# Old Notion "database" pages get a home under the section they belong to.
MOVED = {
    "/databases/work-database/jess": "/creative-tech/jess",
    "/databases/work-database/dataville": "/creative-tech/dataville",
    "/databases/work-database/becoming-l": "/creative-tech/becoming-l",
    "/databases/work-database/creative-technyc-media-lab": "/creative-tech/cr-safe",
    "/databases/work-database/hardware-installations": "/creative-tech/hardware-installations",
    "/databases/work-database/fundamental-surgery": "/ar-vr/fundamental-surgery",
    "/databases/work-database/ownpath": "/design/ownpath",
}
OLD_DOMAINS = ("https://chaky.space", "http://chaky.space", "https://chaky.works", "http://chaky.works",
               "https://www.chaky.space")

report = {"missing_images": [], "unknown_blocks": [], "gifs_to_video": [], "pages": []}


def page_file(p):
    return "index" if p == "/" else p.strip("/").replace("/", "__")


def new_path(p):
    p = p.rstrip("/") or "/"
    return MOVED.get(p, p)


def page_dir(p):
    return PAGES + ("/home" if p == "/" else p)


def media_key(url):
    url = htmllib.unescape(url)
    m = re.search(r"imagedelivery/[^/]+/([0-9a-f-]{36})/", url)
    if m:
        return m.group(1)
    m = re.search(r"c1000a90-84bb-44d4-9fe4-6222c9dc6212/(.+?)(?:\?|$)", url)
    if m:
        return m.group(1).replace("/", "__")
    return None


def media_file(url):
    k = media_key(url)
    if k and k in manifest and "file" in manifest[k]:
        return f"{MEDIA}/{manifest[k]['file']}"
    return None


def clean_name(url, fallback):
    """Readable filename from the Notion image URL, e.g. .../<uuid>/Photo_Rounded-01/public -> photo-rounded-01"""
    url = htmllib.unescape(url)
    m = re.search(r"imagedelivery/[^/]+/[0-9a-f-]{36}/([^/]+)/", url) or re.search(r"/([^/?]+?)(?:\.\w+)?(?:\?|$)", url)
    name = unquote(m.group(1)) if m else fallback
    name = re.sub(r"\.(png|jpe?g|gif|webp|mp4)$", "", name, flags=re.I)
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()[:50]
    return name or fallback


class Page:
    def __init__(self, old):
        self.old = old
        self.path = new_path(old)
        self.dir = page_dir(self.path)
        self.public = PUBLIC + ("/home" if self.path == "/" else self.path)
        self.used = set()
        self.cover = None

    def unique(self, base, ext):
        n, i = base, 2
        while n + ext in self.used:
            n, i = f"{base}-{i}", i + 1
        self.used.add(n + ext)
        return n + ext

    def add_image(self, url, fallback="image"):
        """Copy an image next to the page. Returns ('img', relpath) or ('video', publicpath, w, h) or None."""
        src = media_file(url)
        if not src:
            report["missing_images"].append({"page": self.path, "url": htmllib.unescape(url)[:200]})
            return None
        ext = os.path.splitext(src)[1].lower()
        base = clean_name(url, fallback)
        if ext == ".gif":
            os.makedirs(self.public, exist_ok=True)
            name = self.unique(base, ".mp4")
            out = f"{self.public}/{name}"
            if not os.path.exists(out):
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-movflags", "faststart",
                                "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                                "-c:v", "libx264", "-crf", "24", "-an", out], check=True)
            w, h = gif_size(src)
            report["gifs_to_video"].append({"page": self.path, "gif_kb": os.path.getsize(src) // 1024,
                                            "mp4_kb": os.path.getsize(out) // 1024})
            return ("video", "/media" + out.split("/public/media", 1)[1], w, h)
        os.makedirs(self.dir, exist_ok=True)
        name = self.unique(base, ext)
        shutil.copyfile(src, f"{self.dir}/{name}")
        return ("img", "./" + name)


def gif_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    w, h = out.strip().split("\n")[0].split(",")
    return int(w), int(h)


def attr(v):
    return '"' + str(v).replace("\\", "\\\\").replace('"', "&quot;") + '"'


# ---------- inline text ----------
MD_ESC = re.compile(r"([\\`*_\[\]<>])")


def esc(text):
    return MD_ESC.sub(r"\\\1", text)


def wrap(marker_open, inner, marker_close=None):
    """Put emphasis markers around text, keeping surrounding spaces outside the markers."""
    marker_close = marker_close if marker_close is not None else marker_open
    if not inner.strip():
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    return f"{lead}{marker_open}{inner.strip()}{marker_close}{trail}"


def inline(el, page):
    out = []
    for c in el.children:
        if isinstance(c, NavigableString):
            out.append(esc(str(c)).replace("\n", "\\\n"))
            continue
        if not isinstance(c, Tag):
            continue
        cls = c.get("class", [])
        inner = inline(c, page)
        if c.name == "a":
            href = htmllib.unescape(c.get("href", ""))
            for d in OLD_DOMAINS:
                if href.startswith(d):
                    href = href[len(d):] or "/"
            if href.startswith("/"):
                href = new_path(href.split("#")[0]) + (("#" + href.split("#")[1]) if "#" in href else "")
            out.append(f"[{inner.strip()}]({href})" if inner.strip() else "")
        elif c.name == "strong":
            out.append(wrap("**", inner))
        elif c.name == "em":
            out.append(wrap("*", inner))
        elif c.name in ("del", "s"):
            out.append(wrap("~~", inner))
        elif c.name == "u":
            out.append(wrap("<u>", inner, "</u>"))
        elif c.name == "code":
            out.append(wrap("`", c.get_text()))
        elif c.name == "br":
            out.append("\\\n")
        elif c.name == "span" and "color-gray" in cls:
            out.append(wrap('<span class="gray">', inner, "</span>"))
        elif c.name in ("svg", "img") or "notion-property__title__icon-wrapper" in cls:
            continue
        else:
            out.append(inner)
    text = "".join(out)
    # join neighbouring runs of the same formatting: ~~a~~~~b~~ -> ~~ab~~
    for m in ("~~", "**"):
        text = text.replace(m + m, "").replace(f"{m} {m}", " ")
    return text


# ---------- blocks ----------
def fence_len(md):
    runs = [len(m.group(1)) for m in re.finditer(r"^(:{3,})", md, flags=re.M)]
    return max([2] + runs) + 1


def container(name, body, attrs=""):
    body = body.strip()
    n = max(3, fence_len(body))
    return f"{':' * n}{name}{attrs}\n{body}\n{':' * n}"


def blocks(el, page):
    """Convert the block children of el into a list of markdown chunks."""
    chunks = []
    kids = [k for k in el.children if isinstance(k, Tag)]
    i = 0
    while i < len(kids):
        k = kids[i]
        i += 1
        cls = k.get("class", [])
        c0 = cls[0] if cls else ""
        if c0 in ("notion-heading__anchor", "notion-anchor") or k.name == "style":
            continue
        if c0 == "notion-heading":
            level = int(k.name[1])
            text = re.sub(r"\s*\\\n\s*", " ", inline(k, page)).strip()
            text = re.sub(r"^\*\*(.*)\*\*$", r"\1", text)
            if text:
                chunks.append("#" * level + " " + text)
        elif c0 == "notion-text":
            sem = k if "notion-semantic-string" in cls else k.select_one(".notion-semantic-string")
            text = inline(sem, page).strip() if sem else ""
            # Notion line breaks: blank lines become new paragraphs, none at the start or end
            text = re.sub(r"(?:\\\n\s*){2,}", "\n\n", text)
            text = re.sub(r"^(?:\\\n\s*)+|(?:\s*\\\n)+$", "", text).strip()
            text = re.sub(r"\s*\\$", "", text)
            if text:
                chunks.append(text)
        elif c0 == "notion-divider":
            chunks.append("---")
        elif c0 == "notion-image":
            img = k.select_one("img")
            if not img:
                continue
            url = k.select_one("[data-full-size]")
            url = url["data-full-size"] if url else img.get("src", "")
            alt = (img.get("alt") or "").strip()
            alt = "" if alt.lower() in ("image", "untitled") else alt
            cap = k.select_one(".notion-caption")
            cap = inline(cap, page).strip() if cap else ""
            res = page.add_image(url)
            if res is None:
                chunks.append(f"<!-- missing image: {clean_name(url, 'image')} (restore from the Notion export) -->")
            elif res[0] == "img":
                title = f' "{cap}"' if cap else ""
                md = f"![{esc(alt)}]({res[1]}{title})"
                try:
                    shown = float(img.get("width") or 0)
                except ValueError:
                    shown = 0
                # Notion shows images full width unless they were resized smaller
                if 0 < shown < 500:
                    md = container("figure", md, f'{{width="{round(shown)}"}}')
                chunks.append(md)
            else:
                a = f'src={attr(res[1])} width="{res[2]}" height="{res[3]}"'
                if alt:
                    a += f" alt={attr(alt)}"
                chunks.append(f"::loop{{{a}}}")
            if cap and res and res[0] != "img":
                chunks.append(f"*{cap}*")
        elif c0 == "notion-column-list":
            cols, any_content = [], False
            for col in k.find_all(class_="notion-column", recursive=False):
                m = re.findall(r"\*\s*([0-9.]+)\)", col.get("style", ""))
                w = f'{{width="{float(m[-1]):.4g}"}}' if m else ""
                inner = "\n\n".join(blocks(col, page))
                any_content = any_content or bool(inner.strip())
                cols.append(container("column", inner or "&nbsp;", w))
            if any_content:
                chunks.append(container("columns", "\n\n".join(cols)))
        elif c0 == "notion-embed":
            ifr = k.select_one("iframe")
            if not ifr:
                report["unknown_blocks"].append({"page": page.path, "block": "embed-without-iframe"})
                continue
            src = htmllib.unescape(ifr["src"])
            wrapper = k.select_one(".notion-embed__container__wrapper").get("style", "")
            cont = k.select_one(".notion-embed__container").get("style", "")
            a = f"src={attr(src)}"
            m = re.search(r"padding-bottom:([0-9.]+)%", wrapper)
            if m:
                a += f' ratio="{m.group(1)}"'
            m = re.search(r"height:([0-9.]+)px", wrapper)
            if m:
                a += f' height="{m.group(1)}"'
            m = re.search(r"width:([0-9.]+)px", cont)
            if m:
                a += f' width="{m.group(1)}"'
            chunks.append(f"::embed{{{a}}}")
        elif c0 == "notion-video":
            s = k.select_one("source") or k.select_one("video")
            src = s.get("src", "") if s else ""
            f = media_file(src)
            if not f:
                report["missing_images"].append({"page": page.path, "url": src})
                continue
            os.makedirs(page.public, exist_ok=True)
            name = page.unique(clean_name(src, "video"), ".mp4")
            shutil.copyfile(f, f"{page.public}/{name}")
            a = f"src={attr('/media' + page.public.split('/public/media', 1)[1] + '/' + name)}"
            vw = (k.select_one("video").get("width") or "") if k.select_one("video") else ""
            if vw.endswith("px"):
                a += f' width="{round(float(vw[:-2]))}"'
            chunks.append(f"::video{{{a}}}")
        elif c0 == "notion-bookmark":
            a = k.select_one("a")
            t = k.select_one(".notion-bookmark__title")
            d = k.select_one(".notion-bookmark__description")
            s = f"url={attr(htmllib.unescape(a['href']))}"
            if t:
                s += f" title={attr(t.get_text(strip=True))}"
            if d:
                s += f" description={attr(d.get_text(strip=True))}"
            chunks.append(f"::bookmark{{{s}}}")
        elif c0 in ("notion-bulleted-list", "notion-numbered-list"):
            n = 1
            lines = []
            for li in k.find_all(class_="notion-list-item", recursive=False):
                sem = li.select_one(".notion-semantic-string")
                marker = f"{n}." if c0 == "notion-numbered-list" else "-"
                lines.append(f"{marker} {inline(sem, page).strip() if sem else ''}")
                n += 1
            chunks.append("\n".join(lines))
        elif c0 == "notion-to-do":
            lines = []
            j = i - 1
            while j < len(kids) and "notion-to-do" in kids[j].get("class", []):
                td = kids[j]
                done = bool(td.select_one(".notion-checkbox.checked, .checked"))
                sem = td.select_one(".notion-semantic-string")
                lines.append(f"- [{'x' if done else ' '}] {inline(sem, page).strip() if sem else ''}")
                j += 1
            i = j
            chunks.append("\n".join(lines))
        elif c0 == "notion-collection":
            g = k.select_one(".notion-collection-gallery")
            if not g:
                report["unknown_blocks"].append({"page": page.path, "block": "collection-" + " ".join(cls)})
                continue
            items = []
            for card in g.select(".notion-collection-card"):
                href = new_path(card.select_one("a.notion-collection-card__anchor")["href"])
                items.append(href)
                full = card.select_one("[data-full-size]")
                if full:
                    COVERS.setdefault(href, full["data-full-size"])
            layout = "bento" if page.path == "/" else "grid"
            chunks.append(f'::gallery{{layout="{layout}" items={attr(" ".join(items))}}}')
        elif c0 in ("notion-toggle", "notion-code"):
            continue  # template instructions, hidden on the live site
        else:
            report["unknown_blocks"].append({"page": page.path, "block": " ".join(cls)[:80] or k.name})
    return chunks


COVERS = {}
pages = []
for d in (PAGES, PUBLIC):  # generated output: start clean
    shutil.rmtree(d, ignore_errors=True)
scope = json.load(open(f"{REPO}/archive/scope.json"))
for old in scope:
    soup = BeautifulSoup(open(f"{SNAP}/{page_file(old)}.html").read(), "html.parser")
    root = soup.select_one(".notion-root")
    page = Page(old)
    page.chunks = blocks(root, page)
    h1 = root.select_one("h1.notion-heading")
    # Notion page name (short, used on cards); the homepage's <title> is the site tagline, so use its heading
    page.title = (h1.get_text(" ", strip=True) if old == "/" or not soup.title else soup.title.get_text(strip=True))
    desc = soup.select_one('meta[name="description"]')
    page.description = desc["content"].strip() if desc and desc.get("content") else ""
    pages.append(page)

# covers for gallery cards live next to the project they belong to
by_path = {p.path: p for p in pages}
for href, url in COVERS.items():
    p = by_path.get(href)
    if not p:
        report["unknown_blocks"].append({"page": href, "block": "gallery card for page not in scope"})
        continue
    res = p.add_image(url, "cover")
    if res and res[0] == "img":
        p.cover = res[1]
    elif res:
        p.cover_video = res[1]

for p in pages:
    fm = [f"title: {json.dumps(p.title, ensure_ascii=False)}"]
    if p.description and p.path == "/":
        fm.append(f"description: {json.dumps(p.description, ensure_ascii=False)}")
    if p.cover:
        fm.append(f"cover: {p.cover}")
    if getattr(p, "cover_video", None):
        fm.append(f"coverVideo: {p.cover_video}")
    if p.old != p.path:
        fm.append(f"oldPath: {p.old}")
    os.makedirs(p.dir, exist_ok=True)
    body = "\n\n".join(p.chunks).strip() + "\n"
    open(f"{p.dir}/index.md", "w").write("---\n" + "\n".join(fm) + "\n---\n\n" + body)
    report["pages"].append({"old": p.old, "new": p.path, "blocks": len(p.chunks)})

json.dump(report, open(f"{REPO}/archive/conversion-report.json", "w"), indent=1)
print("pages:", len(pages), "| missing media:", len(report["missing_images"]),
      "| unknown blocks:", len(report["unknown_blocks"]), "| gifs->mp4:", len(report["gifs_to_video"]))
for u in report["unknown_blocks"]:
    print("  unknown:", u)
for m in report["missing_images"]:
    print("  missing:", m["page"], m["url"][:100])
