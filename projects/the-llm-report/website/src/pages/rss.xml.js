// RSS Feed — The LLM Report
// Generated dynamically from the editions content collection

const SITE_URL = 'https://thellmreport.com';

export async function GET() {
  // In production: import editions from content collection
  // For now: minimal valid RSS feed
  const editions = [];

  const items = editions.map(ed => `
    <item>
      <title><![CDATA[${ed.title}]]></title>
      <link>${SITE_URL}/editions/${ed.slug}/</link>
      <guid isPermaLink="true">${SITE_URL}/editions/${ed.slug}/</guid>
      <pubDate>${new Date(ed.date).toUTCString()}</pubDate>
      <description><![CDATA[${ed.description || ''}]]></description>
    </item>`
  ).join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>The LLM Report</title>
    <link>${SITE_URL}</link>
    <description>Autonomous AI industry intelligence — 4x per week.</description>
    <language>en-us</language>
    <managingEditor>aifactory.ops@outlook.com (The LLM Report)</managingEditor>
    <atom:link href="${SITE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
    },
  });
}
