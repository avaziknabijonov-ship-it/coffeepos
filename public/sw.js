/* CoffeePOS first-party offline shell. Only public static assets are cached.
   API traffic, receipts and customer data are never cached by the service worker. */
const CACHE_NAME = 'coffeepos-static-v1'
const SHELL = ['/', '/favicon.svg']

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(
      names.filter(name => name.startsWith('coffeepos-static-') && name !== CACHE_NAME)
        .map(name => caches.delete(name))
    )).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', event => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/healthz') || url.pathname.startsWith('/sw.js')) return

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then(async response => {
      if (response.ok) {
        const cache = await caches.open(CACHE_NAME)
        await cache.put('/', response.clone())
      }
      return response
    }).catch(async () => {
      const cache = await caches.open(CACHE_NAME)
      return await cache.match('/') || Response.error()
    }))
    return
  }
  if (!url.pathname.startsWith('/assets/') && !SHELL.includes(url.pathname)) return
  event.respondWith(caches.open(CACHE_NAME).then(async cache => {
    const saved = await cache.match(request)
    if (saved) return saved
    const response = await fetch(request)
    if (response.ok) await cache.put(request, response.clone())
    return response
  }))
})
