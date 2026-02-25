import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://thellmreport.com',
  integrations: [
    sitemap({
      filter: (page) => !page.includes('/drafts/'),
    }),
  ],
  build: {
    // No source maps in production
    sourcemap: false,
    // Inline stylesheets under 4KB
    inlineStylesheets: 'auto',
  },
  vite: {
    build: {
      sourcemap: false,
      cssMinify: true,
    },
  },
});
