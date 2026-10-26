# chaky.space

Personal portfolio, moved off Notion + Super.so onto a free static site (Astro, hosted on GitHub Pages).

## Editing

Each page is a Markdown file in `src/content/pages/<address>/index.md`, with its images in the same folder.
Edit on github.com or locally, commit, push to `main`, and the site rebuilds automatically (about 2 minutes).
The syntax for columns, galleries, videos and embeds is in [CONTENT-FORMAT.md](CONTENT-FORMAT.md).

## Running locally

Needs Node 22 or newer.

```bash
npm install
npm run dev        # live preview at http://localhost:4321
npm run build      # production build into dist/
```

## Layout

| Path | What it is |
|---|---|
| `src/content/pages/` | all page content (Markdown + images) |
| `public/media/` | videos (including GIFs converted to MP4) |
| `public/fonts/` | Satoshi font (free, ITF Free Font License, see `Satoshi-LICENSE.txt`) |
| `src/styles/site.css` | the whole design |
| `src/lib/remark-blocks.mjs` | turns `::gallery`, `::::columns`, `::embed` etc. into HTML |
| `src/layouts/Base.astro` | navigation, page shell, image lightbox |
| `astro.config.mjs` | redirects from old Notion addresses |
| `archive/super-snapshot/` | the old site's HTML as it was on 2026-10-26 (reference) |
| `archive/media/` | full-size originals downloaded from Super (local only, not in git) |
| `tools/migration/` | the one-off scripts that did the backup and conversion |

## Moving the domain (chaky.space) here

1. In the repo: Settings → Pages → Custom domain → `chaky.space`, then tick "Enforce HTTPS" once it's offered.
   Delete the `BASE_PATH` repository variable (Settings → Secrets and variables → Actions → Variables) and re-run the deploy.
2. At Namecheap (Domain List → chaky.space → Advanced DNS):
   - Replace the `A` record `@ → 76.76.21.21` with four `A` records for `@`:
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - Change the `CNAME` record `www → cname.super.so` to `www → aboltaabol.github.io`
   - **Leave the MX and TXT records alone** — they run the email forwarding.
3. Wait for DNS (minutes to a few hours), check the site, then cancel Super.

## Known gaps from the migration

- **CR Safe**: 3 GIFs were already broken on the old site (expired Notion links). Restore them from a
  Notion export (Settings → Export → Markdown & CSV, include subpages and files) — search the page for `missing image`.
- Images from Super are at most 1366 px wide; the Notion export has the full-size originals if needed.
- Search engines are blocked (`noindex` in `src/layouts/Base.astro`), as on the old site.
