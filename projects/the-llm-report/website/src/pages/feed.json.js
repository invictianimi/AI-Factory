// JSON Feed 1.1 — The LLM Report
import { getCollection } from 'astro:content';

const SITE_URL = 'https://thellmreport.com';

export async function GET() {
  const allEditions = await getCollection('editions');
  const editions = allEditions.sort((a, b) => b.data.date.localeCompare(a.data.date));

  const feed = {
    version: 'https://jsonfeed.org/version/1.1',
    title: 'The LLM Report',
    home_page_url: SITE_URL,
    feed_url: `${SITE_URL}/feed.json`,
    description: 'Autonomous AI industry intelligence — 4x per week.',
    language: 'en-US',
    authors: [{ name: 'The LLM Report', url: SITE_URL }],
    items: editions.map(entry => ({
      id: `${SITE_URL}/editions/${entry.slug}/`,
      url: `${SITE_URL}/editions/${entry.slug}/`,
      title: entry.data.title,
      summary: entry.data.description || '',
      date_published: new Date(entry.data.date + 'T12:00:00Z').toISOString(),
      tags: entry.data.tags || [],
    })),
  };

  return new Response(JSON.stringify(feed, null, 2), {
    headers: { 'Content-Type': 'application/feed+json; charset=utf-8' },
  });
}
