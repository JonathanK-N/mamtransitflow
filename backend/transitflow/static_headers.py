def pwa_headers(headers, path, url):
    if url in {'/sw.js', '/manifest.webmanifest', '/index.html'}:
        headers['Cache-Control'] = 'no-cache'
