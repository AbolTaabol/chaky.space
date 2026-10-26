import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Every page is a folder with an index.md; the folder path is the page's address.
// The homepage lives in pages/home/.
const pages = defineCollection({
  loader: glob({
    pattern: '**/index.md',
    base: './src/content/pages',
    generateId: ({ entry }) => entry.replace(/\/?index\.md$/, ''),
  }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      description: z.string().optional(),
      cover: image().optional(), // image used for this page's card in galleries
      oldPath: z.string().optional(), // address on the old Super site, for reference
    }),
});

export const collections = { pages };
