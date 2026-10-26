# Content format

Every page on the site is one Markdown file. This document is the contract: anything that writes these files
by hand or with a tool (for example a future Notion → Markdown exporter) should produce exactly this.

## Where pages live

```
src/content/pages/
  home/index.md                     → /            (the homepage)
  about/index.md                    → /about
  creative-tech/index.md            → /creative-tech
  creative-tech/whale-tales/index.md → /creative-tech/whale-tales
  creative-tech/whale-tales/*.png   images used by that page
public/media/<page path>/*.mp4      videos used by that page (served as /media/<page path>/…)
```

The folder path is the page address. To add a project, make a new folder with an `index.md` and its images.

## Front matter

```yaml
---
title: "Whale Tales"          # required. Short name: browser tab and gallery cards
cover: ./cover.png            # optional. Image for this page's card in galleries (relative to the file)
description: "…"              # optional. Search/social description
oldPath: /databases/…         # optional. Address on the old Super site (reference only)
---
```

## Body

Plain Markdown (GitHub flavoured: tables, `~~strike~~`, `- [x] task lists`), plus:

| Notion block | Markdown |
|---|---|
| Page title heading | `# Title` as the first line of the body |
| Heading 1/2/3 | `#`, `##`, `###` (`##` is shown in capitals, used as row labels) |
| Text | paragraphs; links `[text](url)`; site links start with `/` |
| Gray text | `<span class="gray">text</span>` |
| Underline | `<u>text</u>` |
| Divider | `---` |
| Image (full width) | `![alt text](./name.png)` — file next to `index.md` |
| Image resized smaller | `:::figure{width="240"}` + image + `:::` |
| Columns | see below |
| Video file | `::video{src="/media/<page path>/clip.mp4" width="400"}` (`width` optional, px) |
| GIF | converted to MP4: `::loop{src="/media/<page path>/clip.mp4" width="600" height="1300"}` |
| Embed (YouTube, Drive, SoundCloud…) | `::embed{src="https://…" ratio="56.25"}` (ratio = height/width × 100) or `height="450"` (+ optional `width="500"`) |
| Bookmark | `::bookmark{url="https://…" title="…" description="…"}` |
| Gallery of linked pages | `::gallery{layout="grid" items="/creative-tech/jess /creative-tech/dataville"}` — `layout="bento"` is the 4-card homepage layout. Cards use each page's `title` and `cover`. |
| Toggle / code / callout | not used on the site |

### Columns

Widths are fractions (Notion's column widths). The outer fence needs more colons than the inner ones:

```md
::::columns
:::column{width="0.1875"}
## About
:::

:::column{width="0.8125"}
Text…
:::
::::
```

If a column itself contains a `:::figure`, give the column 4 colons and the columns block 5.
An empty spacer column is written as `&nbsp;` and is hidden on phones.

## Images and video

- Put the original image next to `index.md`. The build makes small WebP copies in several sizes.
- Animated GIFs are slow: convert to MP4 first
  `ffmpeg -i in.gif -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -crf 24 -an out.mp4`
  and use `::loop`.
- Keep single files under 50 MB (GitHub's limit is 100 MB).

The directives are implemented in `src/lib/remark-blocks.mjs` and styled in `src/styles/site.css`.
