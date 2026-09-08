'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import {
  LiveSession,
  createLiveSession,
  deleteLiveSession,
  getCourseLiveSessions,
} from '@services/courses/liveSessions'
import { Trash2, Video } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

/**
 * Scheduled live video sessions — an embedded meeting link (Zoom/Meet/
 * Teams/any http(s) URL) plus a scheduled time, not a native in-app video
 * call. See apps/api's services/courses/live_sessions.py module docstring
 * for the scope decision. Sessions also appear on the student's ICS
 * calendar feed (services/users/calendar_feed.py) with the meeting link
 * as a clickable join URL.
 */
export default function EditCourseLiveSessions({ orgslug }: { orgslug: string }) {
  const { t } = useTranslation()
  const course = useCourse() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const course_uuid = course?.courseStructure?.course_uuid

  const [sessions, setSessions] = useState<LiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [meetingUrl, setMeetingUrl] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    if (!course_uuid) return
    setLoading(true)
    try {
      const res = await getCourseLiveSessions(course_uuid, access_token)
      setSessions(res || [])
    } catch {
      // empty state on failure
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [course_uuid, access_token])

  const handleCreate = async () => {
    if (!course_uuid || !title.trim() || !meetingUrl.trim() || !startTime) return
    setCreating(true)
    try {
      await createLiveSession(
        course_uuid,
        {
          title: title.trim(),
          meeting_url: meetingUrl.trim(),
          start_time: startTime,
          end_time: endTime || null,
        },
        access_token
      )
      setTitle('')
      setMeetingUrl('')
      setStartTime('')
      setEndTime('')
      toast.success(t('dashboard.courses.live_sessions.created', { defaultValue: 'Live session scheduled.' }))
      await load()
    } catch (err: any) {
      toast.error(err?.message || t('common.something_went_wrong'))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (session_uuid: string) => {
    if (!course_uuid) return
    try {
      await deleteLiveSession(course_uuid, session_uuid, access_token)
      setSessions((prev) => prev.filter((s) => s.session_uuid !== session_uuid))
    } catch {
      toast.error(t('common.something_went_wrong'))
    }
  }

  return (
    <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Video size={16} className="text-gray-500" />
          <p className="text-sm font-bold text-gray-900">
            {t('dashboard.courses.live_sessions.title', { defaultValue: 'Live sessions' })}
          </p>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed">
          {t('dashboard.courses.live_sessions.description', {
            defaultValue:
              "Schedule a live class with any meeting link (Zoom, Google Meet, Teams, ...). Students see the schedule on this course and in their calendar feed with a Join link — the call itself happens on the meeting platform, not inside St. Joseph's Placements and Training Cell.",
          })}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input
            type="text"
            placeholder={t('dashboard.courses.live_sessions.title_placeholder', { defaultValue: 'Session title' })}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="url"
            placeholder={t('dashboard.courses.live_sessions.url_placeholder', { defaultValue: 'Meeting link (https://...)' })}
            value={meetingUrl}
            onChange={(e) => setMeetingUrl(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="datetime-local"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            placeholder={t('dashboard.courses.live_sessions.end_time', { defaultValue: 'End time (optional)' })}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          type="button"
          onClick={handleCreate}
          disabled={creating || !title.trim() || !meetingUrl.trim() || !startTime}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
        >
          {creating ? t('common.loading', { defaultValue: 'Loading…' }) : t('dashboard.courses.live_sessions.schedule_button', { defaultValue: 'Schedule' })}
        </button>

        {!loading && sessions.length > 0 && (
          <div className="mt-2 space-y-2 border-t border-gray-100 pt-3">
            {sessions.map((s) => (
              <div key={s.session_uuid} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                <div>
                  <p className="text-xs font-semibold text-gray-900">{s.title}</p>
                  <p className="text-[11px] text-gray-500">
                    {new Date(s.start_time).toLocaleString()}
                    {s.end_time ? ` – ${new Date(s.end_time).toLocaleString()}` : ''}
                  </p>
                  <a
                    href={s.meeting_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] text-blue-600 hover:underline break-all"
                  >
                    {s.meeting_url}
                  </a>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(s.session_uuid)}
                  className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 shrink-0"
                  aria-label="Cancel"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
