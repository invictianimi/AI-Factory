// Google News Sitemap — The LLM Report
// Only includes articles published within the last 48 hours

const SITE_URL = 'https://thellmreport.com';

export async function GET() {
  // In production: filter editions by date < 48 hours old
  const recentEditions = [];
  const cutoff = new Date(Date.now() - 48 * 60 * 60 * 1000);

  const urls = recentEditions
    .filter(ed => new Date(ed.date) >= cutoff)
    .map(ed => `
  <url>
    <loc>${SITE_URL}/editions/${ed.slug}/</loc>
    <news:news>
      <news:publication>
        <news:name>The LLM Report</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${new Date(ed.date).toISOString()}</news:publication_date>
      <news:title><![CDATA[${ed.title}]]></news:title>
    </news:news>
  </url>`
    ).join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  ${urls}
</urlset>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
