/**
 * Clears every cache the offline service worker (public/sw.js) maintains.
 *
 * KNOWN LIMITATION this exists to narrow, not eliminate: the service worker's
 * Cache API storage has no concept of "which user" cached a response — it is
 * keyed only by origin, the same way browser disk cache is. On a SHARED
 * device (a library or lab computer) two different accounts logged in
 * sequentially in the same browser profile could otherwise see each other's
 * cached restricted course content while offline. Calling this on every
 * sign-out (see components/Contexts/AuthContext.tsx's handleSignOut, the
 * standalone signOut(), and the cross-tab LOGOUT broadcast handler) closes
 * that gap for anyone who actually logs out — it does NOT protect a user who
 * simply closes the tab without signing out first. That residual risk is
 * disclosed, not fixed, in PENDING_FEATURES.md.
 */
export async function clearOfflineCaches(): Promise<void> {
  if (typeof window === 'undefined' || !('caches' in window)) return
  try {
    const keys = await caches.keys()
    await Promise.all(keys.map((key) => caches.delete(key)))
  } catch {
    // Best-effort: a cache-clear failure must never block logout.
  }
}
