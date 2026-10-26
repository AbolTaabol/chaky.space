// Turns the site's Markdown "directives" into HTML. See CONTENT-FORMAT.md for the syntax.
//
//   ::::columns / :::column{width="0.25"}   side-by-side columns (Notion column lists)
//   :::figure{width="240"}                 keeps an image smaller than full width
//   ::gallery{layout="grid|bento" items="/a /b"}  cards linking to other pages, using their `cover`
//   ::embed{src="…" ratio="56.25" | height="450" width="500"}  iframe (YouTube, SoundCloud, Drive…)
//   ::video{src="/media/…mp4" width="400"}  video with controls (width is optional, in px)
//   ::loop{src="/media/…mp4" width height}  silent looping video (used instead of GIFs)
//   ::bookmark{url title description}       link card
import fs from 'node:fs';
import path from 'node:path';
import { visit } from 'unist-util-visit';

const esc = (s = '') =>
  String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function frontmatter(file) {
  const text = fs.readFileSync(file, 'utf8');
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  const get = (key) => {
    const m = fm && fm[1].match(new RegExp(`^${key}:\\s*(.+)$`, 'm'));
    if (!m) return undefined;
    const v = m[1].trim();
    return v.startsWith('"') ? JSON.parse(v) : v;
  };
  return { title: get('title'), cover: get('cover') };
}

export default function remarkBlocks({ base = '/' } = {}) {
  const prefix = base.replace(/\/$/, '');
  const withBase = (url) => (url && url.startsWith('/') && !url.startsWith('//') ? prefix + url : url);

  return (tree, file) => {
    const filePath = file.path || file.history?.[0] || '';
    const pagesRoot = filePath.includes('/src/content/pages/')
      ? filePath.slice(0, filePath.indexOf('/src/content/pages/') + '/src/content/pages'.length)
      : null;

    // site-internal links get the base path (only matters for the github.io preview)
    visit(tree, 'link', (node) => {
      node.url = withBase(node.url);
    });

    visit(tree, (node, index, parent) => {
      if (!['containerDirective', 'leafDirective', 'textDirective'].includes(node.type)) return;
      if (node.type === 'textDirective') {
        // ordinary text like "Note:this" — put the colon back
        const label = node.children.map((c) => c.value || '').join('');
        parent.children[index] = { type: 'text', value: `:${node.name}${label ? `[${label}]` : ''}` };
        return;
      }
      const a = node.attributes || {};

      if (node.name === 'columns') {
        const cols = node.children.filter((c) => c.type === 'containerDirective' && c.name === 'column');
        const widths = cols.map((c) => parseFloat(c.attributes?.width) || 1);
        node.data = {
          hName: 'div',
          hProperties: { className: ['columns'], style: `--cols: ${widths.map((w) => `${w}fr`).join(' ')}` },
        };
        return;
      }
      if (node.name === 'figure') {
        const w = parseFloat(a.width);
        node.data = { hName: 'div', hProperties: { className: ['figure'], style: w ? `max-width:${w}px` : undefined } };
        return;
      }
      if (node.name === 'column') {
        const only = node.children.length === 1 && node.children[0];
        const spacer = only && only.type === 'paragraph' && /^\s*$/.test(only.children.map((c) => c.value || '').join(''));
        node.data = { hName: 'div', hProperties: { className: spacer ? ['column', 'spacer'] : ['column'] } };
        return;
      }

      let html = null;
      if (node.name === 'embed') {
        const frame = a.ratio ? `padding-bottom:${a.ratio}%` : `height:${a.height || 400}px`;
        const max = a.width ? ` style="max-width:${a.width}px"` : '';
        let host = '';
        try { host = new URL(a.src).hostname.replace(/^www\./, ''); } catch {}
        html = `<div class="embed"${max}><div class="embed-frame${a.ratio ? ' ratio' : ''}" style="${frame}"><iframe src="${esc(a.src)}" title="${esc(a.title || host)}" loading="lazy" allowfullscreen allow="autoplay; encrypted-media; picture-in-picture; fullscreen"></iframe></div></div>`;
      } else if (node.name === 'video') {
        const max = a.width ? ` style="max-width:${parseFloat(a.width)}px"` : '';
        html = `<video class="media" src="${esc(withBase(a.src))}"${max} controls preload="metadata" playsinline></video>`;
      } else if (node.name === 'loop') {
        const size = a.width ? ` width="${esc(a.width)}" height="${esc(a.height)}"` : '';
        const label = a.alt ? ` aria-label="${esc(a.alt)}"` : ' aria-hidden="true"';
        html = `<video class="media loop" src="${esc(withBase(a.src))}"${size} autoplay loop muted playsinline preload="metadata"${label}></video>`;
      } else if (node.name === 'bookmark') {
        let host = a.url;
        try { host = new URL(a.url).hostname.replace(/^www\./, ''); } catch {}
        html =
          `<a class="bookmark" href="${esc(a.url)}" target="_blank" rel="noopener">` +
          `<span class="bookmark-title">${esc(a.title || host)}</span>` +
          (a.description ? `<span class="bookmark-desc">${esc(a.description)}</span>` : '') +
          `<span class="bookmark-url">${esc(host)}</span></a>`;
      } else if (node.name === 'gallery') {
        if (!pagesRoot) throw new Error(`::gallery needs a page inside src/content/pages (${filePath})`);
        const here = path.dirname(filePath);
        const cards = (a.items || '').split(/\s+/).filter(Boolean).map((href) => {
          const dir = path.join(pagesRoot, href === '/' ? 'home' : href);
          const md = path.join(dir, 'index.md');
          if (!fs.existsSync(md)) throw new Error(`::gallery item ${href} has no page at ${md}`);
          const { title, cover } = frontmatter(md);
          const children = [];
          if (cover) {
            let rel = path.relative(here, path.join(dir, cover));
            if (!rel.startsWith('.')) rel = './' + rel;
            children.push({ type: 'image', url: rel, alt: '' });
          }
          children.push({ type: 'cardTitle', data: { hName: 'span', hProperties: { className: ['card-title'] } }, children: [{ type: 'text', value: title || href }] });
          return { type: 'link', url: withBase(href), data: { hProperties: { className: ['card'] } }, children };
        });
        parent.children[index] = {
          type: 'gallery',
          data: { hName: 'div', hProperties: { className: ['gallery', a.layout === 'bento' ? 'bento' : 'grid'] } },
          children: cards,
        };
        return;
      } else {
        file.message(`Unknown directive ::${node.name}`, node);
        return;
      }
      parent.children[index] = { type: 'html', value: html };
    });
  };
}
