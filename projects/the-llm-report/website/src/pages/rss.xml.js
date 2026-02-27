// RSS Feed — The LLM Report
import { getCollection } from 'astro:content';

const SITE_URL = 'https://thellmreport.com';

export async function GET() {
  const allEditions = await getCollection('editions');
  const editions = allEditions.sort((a, b) => b.data.date.localeCompare(a.data.date));

  const items = editions.map(entry => `
    <item>
      <title><![CDATA[${entry.data.title}]]></title>
      <link>${SITE_URL}/editions/${entry.slug}/</link>
      <guid isPermaLink="true">${SITE_URL}/editions/${entry.slug}/</guid>
      <pubDate>${new Date(entry.data.date + 'T12:00:00Z').toUTCString()}</pubDate>
      <description><![CDATA[${entry.data.description || ''}]]></description>
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
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
