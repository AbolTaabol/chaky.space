import { defineConfig } from 'astro/config';
import remarkDirective from 'remark-directive';
import remarkBlocks from './src/lib/remark-blocks.mjs';

// BASE_PATH is only set for the temporary preview at aboltaabol.github.io/chaky.space.
// Once chaky.space points at GitHub Pages it is left empty.
const base = process.env.BASE_PATH || '/';

// Old Notion database addresses -> new homes (keeps existing links working)
const moved = {
  '/databases/work-database/jess': '/creative-tech/jess',
  '/databases/work-database/dataville': '/creative-tech/dataville',
  '/databases/work-database/becoming-l': '/creative-tech/becoming-l',
  '/databases/work-database/creative-technyc-media-lab': '/creative-tech/cr-safe',
  '/databases/work-database/hardware-installations': '/creative-tech/hardware-installations',
  '/databases/work-database/fundamental-surgery': '/ar-vr/fundamental-surgery',
  '/databases/work-database/ownpath': '/design/ownpath',
};
const join = (p) => (base.replace(/\/$/, '') + p) || '/';

export default defineConfig({
  site: 'https://chaky.space',
  base,
  trailingSlash: 'ignore',
  image: { layout: 'constrained' },
  markdown: {
    remarkPlugins: [remarkDirective, [remarkBlocks, { base }]],
  },
  redirects: Object.fromEntries(Object.entries(moved).map(([from, to]) => [from, join(to)])),
});
