'use client'
import { useEffect } from 'react'

/**
 * Registers the offline-content service worker (public/sw.js) once per tab.
 * See that file's own docstring for exactly what it caches and why, and
 * PENDING_FEATURES.md for the full offline-support scope decision.
 */
export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!('serviceWorker' in navigator)) return

    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Best-effort: a registration failure (private browsing, an unusual
      // browser) must never block the app from working online.
    })
  }, [])

  return null
}
