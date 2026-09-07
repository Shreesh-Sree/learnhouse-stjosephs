/**
 * Offline course-content service worker.
 *
 * SCOPE DECISION (see PENDING_FEATURES.md for the full writeup): this
 * caches DATA — the course-meta and activity-content API responses a
 * student has already viewed — and static build assets, so a chapter or
 * lesson already opened in this tab keeps working when the network drops
 * (spotty campus wifi, a commute, home broadband hiccups). It deliberately
 * does NOT precache the whole app shell or every course up front, and does
 * NOT support a cold full-page reload while fully offline — that would
 * need a real Workbox/next-pwa build-time integration (a new dependency
 * and a build-config change) that a hand-rolled runtime script can't
 * safely replicate. As long as the tab stays open (or is reopened while
 * still online at least once), previously-viewed content keeps working
 * offline; a genuinely cold load with zero connectivity does not.
 *
 * Read-only: only GET requests are ever cached. No offline write support
 * (quiz answers, submissions) — that is a background-sync problem this
 * does not attempt to solve.
 *
 * Privacy note: this cache is keyed by origin only, like ordinary browser
 * disk cache — it has no notion of "which account" fetched a response. The
 * app clears it on every sign-out (services/offline/clearOfflineCache.ts)
 * to keep a second person on a shared device from reading a previous
 * user's cached restricted content offline; it does NOT protect a user who
 * closes the tab without signing out first. Disclosed, not solved, here.
 */

const CACHE_VERSION = 'v1'
const STATIC_CACHE = `lh-static-${CACHE_VERSION}`
const CONTENT_CACHE = `lh-content-${CACHE_VERSION}`
const CURRENT_CACHES = new Set([STATIC_CACHE, CONTENT_CACHE])

// Path fragments (not full URLs — the API may be same-origin via a proxy or
// on a separate api.* host) worth caching for offline reading. Deliberately
// an ALLOWLIST, not a blocklist: auth, users, payments, tokens, and every
// other endpoint are left completely untouched by this service worker.
const CACHEABLE_API_PATTERNS = [
  '/api/v1/courses/',
  '/api/v1/chapters/',
  '/api/v1/activities/',
]

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys()
      await Promise.all(
        names
          .filter((name) => name.startsWith('lh-') && !CURRENT_CACHES.has(name))
          .map((name) => caches.delete(name))
      )
      await self.clients.claim()
    })()
  )
})

function isCacheableApiRequest(url) {
  return CACHEABLE_API_PATTERNS.some((pattern) => url.pathname.includes(pattern))
}

function isStaticAsset(url) {
  // Next.js content-hashed build output — safe to treat as immutable.
  return url.pathname.startsWith('/_next/static/')
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  const networkPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone())
      }
      return response
    })
    .catch(() => undefined)

  // Serve the cached copy immediately if we have one (instant + works
  // offline); otherwise wait on the network. Either way the cache above
  // gets refreshed in the background when the network call succeeds.
  return cached || (await networkPromise) || new Response(
    JSON.stringify({ detail: 'Offline and no cached copy of this content is available yet.' }),
    { status: 503, headers: { 'Content-Type': 'application/json' } }
  )
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  if (cached) return cached

  const response = await fetch(request)
  if (response && response.ok) {
    cache.put(request, response.clone())
  }
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return // never touch mutating requests

  const url = new URL(request.url)

  if (isCacheableApiRequest(url)) {
    event.respondWith(staleWhileRevalidate(request, CONTENT_CACHE))
    return
  }

  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE))
    return
  }

  // Everything else (navigations, auth, uploads, media, third-party) is left
  // completely untouched — falls through to the browser's normal handling.
})
