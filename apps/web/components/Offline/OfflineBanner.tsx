'use client'
import { WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * A small, dismissible-by-reconnecting banner so a student knows they're
 * viewing cached content rather than assuming something is broken. Purely
 * a `navigator.onLine` indicator — it does not know whether the specific
 * page currently open actually has a cached copy (see public/sw.js).
 */
export default function OfflineBanner() {
  const { t } = useTranslation()
  const [isOffline, setIsOffline] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    setIsOffline(!navigator.onLine)

    const goOffline = () => setIsOffline(true)
    const goOnline = () => setIsOffline(false)
    window.addEventListener('offline', goOffline)
    window.addEventListener('online', goOnline)
    return () => {
      window.removeEventListener('offline', goOffline)
      window.removeEventListener('online', goOnline)
    }
  }, [])

  if (!isOffline) return null

  return (
    <div className="fixed bottom-3 inset-x-0 z-50 flex justify-center pointer-events-none">
      <div className="pointer-events-auto flex items-center gap-1.5 bg-neutral-900 text-white text-xs font-medium px-3 py-1.5 rounded-full shadow-lg">
        <WifiOff size={13} />
        {t('offline.banner', { defaultValue: "You're offline — showing content you've already opened." })}
      </div>
    </div>
  )
}
