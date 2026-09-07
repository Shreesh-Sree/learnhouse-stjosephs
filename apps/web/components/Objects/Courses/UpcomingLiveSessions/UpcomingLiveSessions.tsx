'use client'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getCourseLiveSessions, LiveSession } from '@services/courses/liveSessions'
import { Video } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Student-facing schedule of upcoming live sessions for a course — see
 * apps/api's services/courses/live_sessions.py module docstring for the
 * embedded-meeting-link scope decision (not a native in-app video call).
 * Renders nothing if there are no upcoming sessions, so it never adds an
 * empty box to every course page.
 */
export default function UpcomingLiveSessions({ courseUuid }: { courseUuid: string }) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const [sessions, setSessions] = useState<LiveSession[]>([])

  useEffect(() => {
    if (!courseUuid) return
    let stale = false
    ;(async () => {
      try {
        const res = await getCourseLiveSessions(courseUuid, access_token)
        if (stale) return
        const now = Date.now()
        const upcoming = (res || [])
          .filter((s) => {
            const end = s.end_time ? new Date(s.end_time).getTime() : new Date(s.start_time).getTime()
            return end >= now
          })
          .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
        setSessions(upcoming)
      } catch {
        // silent — this is a supplementary widget, not core content
      }
    })()
    return () => {
      stale = true
    }
  }, [courseUuid, access_token])

  if (sessions.length === 0) return null

  return (
    <div className="mt-4 bg-white rounded-lg nice-shadow p-4 space-y-2">
      <div className="flex items-center gap-2">
        <Video size={16} className="text-gray-500" />
        <p className="text-sm font-bold text-gray-900">
          {t('course.live_sessions.title', { defaultValue: 'Upcoming live sessions' })}
        </p>
      </div>
      <div className="space-y-2">
        {sessions.map((s) => (
          <div key={s.session_uuid} className="flex items-center justify-between bg-gray-50 rounded-md p-2.5">
            <div>
              <p className="text-xs font-semibold text-gray-800">{s.title}</p>
              <p className="text-[11px] text-gray-500">{new Date(s.start_time).toLocaleString()}</p>
            </div>
            <a
              href={s.meeting_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold text-white bg-gray-900 hover:bg-gray-800 rounded-md px-3 py-1.5 shrink-0"
            >
              {t('course.live_sessions.join', { defaultValue: 'Join' })}
            </a>
          </div>
        ))}
      </div>
    </div>
  )
}
