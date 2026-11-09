/* Offline shell for the APEA study hub.
   Strategy:
     - navigations: network-first, fall back to cached index.html
     - same-origin static assets: stale-while-revalidate
     - data JSON: network-first with cache fallback (content updates land promptly,
       but a chapter already read stays available on a plane / in a hospital basement)
*/
const VERSION = 'apea-v4'
const SHELL = `${VERSION}-shell`
const ASSETS = `${VERSION}-assets`
const DATA = `${VERSION}-data`

const CORE = ['/apea/study/', '/apea/study/index.html', '/apea/study/manifest.webmanifest']

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL).then(c => c.addAll(CORE)).catch(() => {}).then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', event => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
        .then(res => {
          const copy = res.clone()
          caches.open(SHELL).then(c => c.put('/apea/study/index.html', copy))
          return res
        })
        .catch(() => caches.match('/apea/study/index.html').then(r => r || caches.match('/apea/study/'))),
    )
    return
  }

  if (url.pathname.includes('/data/')) {
    event.respondWith(
      fetch(request)
        .then(res => {
          if (res.ok) {
            const copy = res.clone()
            caches.open(DATA).then(c => c.put(request, copy))
          }
          return res
        })
        .catch(() => caches.match(request)),
    )
    return
  }

  event.respondWith(
    caches.match(request).then(cached => {
      const network = fetch(request, { cache: 'no-store' })
        .then(res => {
          if (res.ok && (url.pathname.includes('/assets/') || url.pathname.endsWith('.svg') || url.pathname.endsWith('.png'))) {
            const copy = res.clone()
            caches.open(ASSETS).then(c => c.put(request, copy))
          }
          return res
        })
        .catch(() => cached)
      return cached || network
    }),
  )
})
