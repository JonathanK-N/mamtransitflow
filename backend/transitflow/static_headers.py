def pwa_headers(headers, path, url):
    if url in {'/sw.js', '/manifest.webmanifest', '/index.html'}:
        headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        headers['CDN-Cache-Control'] = 'no-store'
        headers['Cloudflare-CDN-Cache-Control'] = 'no-store'
