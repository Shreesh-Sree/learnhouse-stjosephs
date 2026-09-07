'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getCourseQuizFlags, QuizFlag, QuizFlagStatus, resolveQuizFlag } from '@services/courses/quizFlags'
import { getUriWithOrg } from '@services/config/config'
import { CheckCircle, Flag, X } from 'lucide-react'
import Link from 'next/link'
import React, { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

type EditCourseQuizFlagsProps = {
  orgslug: string
}

const REASON_LABELS: Record<string, string> = {
  incorrect_answer: 'Incorrect answer key',
  unclear_wording: 'Unclear wording',
  typo: 'Typo',
  other: 'Other',
}

/**
 * Instructor review queue for student-flagged quiz questions. Each row
 * snapshots what the student actually saw at flag time (the question can
 * have since been edited or the block deleted), and links back into the
 * activity editor to fix it.
 */
export default function EditCourseQuizFlags({ orgslug }: EditCourseQuizFlagsProps) {
  const { t } = useTranslation()
  const course = useCourse() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const course_uuid = course?.courseStructure?.course_uuid

  const [statusFilter, setStatusFilter] = useState<QuizFlagStatus>('open')
  const [flags, setFlags] = useState<QuizFlag[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!course_uuid) return
    setLoading(true)
    try {
      const res = await getCourseQuizFlags(course_uuid, statusFilter, access_token)
      setFlags(res || [])
    } catch {
      // empty state on failure
    } finally {
      setLoading(false)
    }
  }, [course_uuid, statusFilter, access_token])

  useEffect(() => {
    load()
  }, [load])

  const handleResolve = async (flag_uuid: string, status: QuizFlagStatus) => {
    setBusyId(flag_uuid)
    try {
      await resolveQuizFlag(flag_uuid, status, access_token)
      setFlags((prev) => prev.filter((f) => f.flag_uuid !== flag_uuid))
      toast.success(t('dashboard.courses.quiz_flags.updated', { defaultValue: 'Updated.' }))
    } catch {
      toast.error(t('common.something_went_wrong'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flag size={16} className="text-gray-500" />
            <p className="text-sm font-bold text-gray-900">
              {t('dashboard.courses.quiz_flags.title', { defaultValue: 'Flagged quiz questions' })}
            </p>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as QuizFlagStatus)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none"
          >
            <option value="open">{t('dashboard.courses.quiz_flags.status_open', { defaultValue: 'Open' })}</option>
            <option value="resolved">{t('dashboard.courses.quiz_flags.status_resolved', { defaultValue: 'Resolved' })}</option>
            <option value="dismissed">{t('dashboard.courses.quiz_flags.status_dismissed', { defaultValue: 'Dismissed' })}</option>
          </select>
        </div>

        {loading ? (
          <p className="text-xs text-gray-400">{t('common.loading', { defaultValue: 'Loading…' })}</p>
        ) : flags.length === 0 ? (
          <p className="text-xs text-gray-400 py-4 text-center">
            {t('dashboard.courses.quiz_flags.empty', { defaultValue: 'Nothing here.' })}
          </p>
        ) : (
          <div className="space-y-3 border-t border-gray-100 pt-3">
            {flags.map((flag) => (
              <div key={flag.flag_uuid} className="bg-gray-50 rounded-lg p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                    {REASON_LABELS[flag.reason] || flag.reason}
                  </span>
                  <Link
                    href={getUriWithOrg(orgslug, '') + `/course/${course_uuid?.replace('course_', '')}/activity/${flag.activity_uuid.replace('activity_', '')}`}
                    prefetch={false}
                    className="text-[11px] text-blue-600 hover:underline"
                  >
                    {flag.activity_name}
                  </Link>
                </div>
                <p className="text-xs text-gray-800 font-medium">{flag.question_text_snapshot}</p>
                {flag.note && <p className="text-xs text-gray-500 italic">"{flag.note}"</p>}
                <p className="text-[11px] text-gray-400">
                  {flag.flagged_by
                    ? `${flag.flagged_by.first_name} ${flag.flagged_by.last_name}`.trim() || flag.flagged_by.username
                    : t('dashboard.courses.quiz_flags.unknown_student', { defaultValue: 'A student' })}
                  {' · '}
                  {flag.creation_date}
                </p>
                {statusFilter === 'open' && (
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleResolve(flag.flag_uuid, 'resolved')}
                      disabled={busyId === flag.flag_uuid}
                      className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                    >
                      <CheckCircle size={12} />
                      {t('dashboard.courses.quiz_flags.mark_resolved', { defaultValue: 'Mark resolved' })}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleResolve(flag.flag_uuid, 'dismissed')}
                      disabled={busyId === flag.flag_uuid}
                      className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50"
                    >
                      <X size={12} />
                      {t('dashboard.courses.quiz_flags.dismiss', { defaultValue: 'Dismiss' })}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
