import http from 'node:http';
import { readFileSync } from 'node:fs';

const assets = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/schema.json', ['schema.json', 'application/json; charset=utf-8']],
  ['/TransitFlow.dbml', ['TransitFlow.dbml', 'text/plain; charset=utf-8']],
  ['/MRL_TransitFlow.md', ['MRL_TransitFlow.md', 'text/plain; charset=utf-8']],
].map(([url, [file, type]]) => [url, { body: readFileSync(new URL(`./public/${file}`, import.meta.url)), type }]));
const server = http.createServer((req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");
  if (!['GET', 'HEAD'].includes(req.method)) {
    res.writeHead(405, { Allow: 'GET, HEAD' }); return res.end();
  }
  let pathname;
  try { pathname = new URL(req.url, 'http://localhost').pathname; }
  catch { res.writeHead(400); return res.end(); }
  const asset = pathname === '/health' ? { body: Buffer.from('{"status":"ok"}'), type: 'application/json' }
    : pathname === '/robots.txt' ? { body: Buffer.from('User-agent: *\nDisallow: /\n'), type: 'text/plain' } : assets.get(pathname);
  if (!asset) { res.writeHead(404); return res.end('Not found'); }
  res.writeHead(200, { 'Content-Type': asset.type, 'Content-Length': asset.body.length, 'Cache-Control': 'no-cache' });
  res.end(req.method === 'HEAD' ? undefined : asset.body);
});
server.listen(Number(process.env.PORT || 8080), '0.0.0.0');
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => server.close(() => process.exit(0)));
