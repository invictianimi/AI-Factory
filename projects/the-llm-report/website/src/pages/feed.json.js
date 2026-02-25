// JSON Feed 1.1 — The LLM Report
// https://www.jsonfeed.org/version/1.1/

const SITE_URL = 'https://thellmreport.com';

export async function GET() {
  // In production: import editions from content collection
  const editions = [];

  const feed = {
    version: 'https://jsonfeed.org/version/1.1',
    title: 'The LLM Report',
    home_page_url: SITE_URL,
    feed_url: `${SITE_URL}/feed.json`,
    description: 'Autonomous AI industry intelligence — 4x per week.',
    language: 'en-US',
    authors: [{ name: 'The LLM Report', url: SITE_URL }],
    items: editions.map(ed => ({
      id: `${SITE_URL}/editions/${ed.slug}/`,
      url: `${SITE_URL}/editions/${ed.slug}/`,
      title: ed.title,
      content_html: ed.content || '',
      summary: ed.description || '',
      date_published: new Date(ed.date).toISOString(),
      tags: ed.tags || [],
    })),
  };

  return new Response(JSON.stringify(feed, null, 2), {
    headers: {
      'Content-Type': 'application/feed+json; charset=utf-8',
    },
  });
}
