'use client'
import React from 'react'
import { Calendar, Copy, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getAPIUrl } from '@services/config/config'
import { getCalendarFeedToken, regenerateCalendarFeedToken } from '@services/users/calendar_feed'

/**
 * A subscribable ICS feed of the student's own assignment due dates — the
 * token in the URL is the credential (calendar apps poll unauthenticated),
 * so this is the one place a user can see/copy/rotate it. See the backend
 * service's module docstring for the trust model and the "floating time,
 * single-timezone deployment" caveat.
 */
export default function CalendarFeedSettings() {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const [token, setToken] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const load = React.useCallback(async () => {
    if (!access_token) return
    const res = await getCalendarFeedToken(access_token)
    if (res.success) setToken(res.data.token)
  }, [access_token])

  React.useEffect(() => {
    load()
  }, [load])

  const feedUrl = token ? `${getAPIUrl()}calendar/feed/${token}.ics` : ''

  const handleCopy = async () => {
    if (!feedUrl) return
    await navigator.clipboard.writeText(feedUrl)
    toast.success(t('account.calendar_feed.copied', { defaultValue: 'Link copied.' }))
  }

  const handleRegenerate = async () => {
    if (!access_token) return
    setBusy(true)
    try {
      const res = await regenerateCalendarFeedToken(access_token)
      if (res.success) {
        setToken(res.data.token)
        toast.success(t('account.calendar_feed.regenerated', { defaultValue: 'New link generated — the old one no longer works.' }))
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white rounded-xl nice-shadow p-6 mt-5">
      <div className="flex items-center gap-2 mb-2">
        <Calendar size={16} className="text-gray-500" />
        <p className="text-sm font-bold text-gray-900">
          {t('account.calendar_feed.title', { defaultValue: 'Calendar feed' })}
        </p>
      </div>
      <p className="text-xs text-gray-500 leading-relaxed mb-3">
        {t('account.calendar_feed.description', {
          defaultValue: 'Subscribe in Google Calendar, Outlook, or Apple Calendar to see your assignment due dates. Anyone with this link can see your due dates, so keep it private — regenerate it if it ever leaks.',
        })}
      </p>
      <div className="flex items-center gap-2">
        <input
          type="text"
          readOnly
          value={feedUrl}
          placeholder={t('common.loading', { defaultValue: 'Loading…' })}
          className="flex-1 px-3 py-2 text-xs font-mono text-gray-600 rounded-lg bg-gray-50 border border-gray-200 outline-none"
        />
        <button
          type="button"
          onClick={handleCopy}
          disabled={!feedUrl}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
        >
          <Copy size={13} />
          {t('account.calendar_feed.copy', { defaultValue: 'Copy' })}
        </button>
        <button
          type="button"
          onClick={handleRegenerate}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-rose-700 bg-rose-50 rounded-lg hover:bg-rose-100 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={busy ? 'animate-spin' : ''} />
          {t('account.calendar_feed.regenerate', { defaultValue: 'Regenerate' })}
        </button>
      </div>
    </div>
  )
}
