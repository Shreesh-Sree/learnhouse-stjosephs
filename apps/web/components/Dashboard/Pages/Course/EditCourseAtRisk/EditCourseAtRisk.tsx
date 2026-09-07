'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { AtRiskFlag, AtRiskStudent, getAtRiskStudents } from '@services/courses/atRisk'
import { AlertTriangle } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

type EditCourseAtRiskProps = {
  orgslug: string
}

const FLAG_LABELS: Record<AtRiskFlag, string> = {
  inactive: 'Inactive',
  failing: 'Multiple failing grades',
  missing_assignments: 'Missing overdue work',
  low_progress: 'Low progress',
}

function daysAgoLabel(days: number | null): string {
  if (days === null) return 'never active'
  if (days === 0) return 'today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

/**
 * Instructor-facing at-risk queue: enrolled students showing one or more
 * warning signs (inactivity, failing grades, missing overdue work, low
 * progress after a while enrolled), computed from durable enrollment/
 * grading data — see apps/api's services/courses/at_risk.py module
 * docstring for the exact thresholds and the "no course schedule model"
 * scope decision behind the low-progress signal. A student with no signal
 * is simply not listed.
 */
export default function EditCourseAtRisk({ orgslug }: EditCourseAtRiskProps) {
  const { t } = useTranslation()
  const course = useCourse() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const course_uuid = course?.courseStructure?.course_uuid

  const [students, setStudents] = useState<AtRiskStudent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!course_uuid) return
    let stale = false
    ;(async () => {
      setLoading(true)
      try {
        const res = await getAtRiskStudents(course_uuid, access_token)
        if (!stale) setStudents(res || [])
      } catch {
        // empty state on failure
      } finally {
        if (!stale) setLoading(false)
      }
    })()
    return () => {
      stale = true
    }
  }, [course_uuid, access_token])

  return (
    <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} className="text-gray-500" />
          <p className="text-sm font-bold text-gray-900">
            {t('dashboard.courses.at_risk.title', { defaultValue: 'At-risk students' })}
          </p>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed">
          {t('dashboard.courses.at_risk.description', {
            defaultValue:
              'Students showing warning signs in this course: inactivity, multiple failing grades, missing overdue assignments, or low progress after a while enrolled. This is a heuristic, not a grade — use it to decide who to check in with.',
          })}
        </p>

        {loading ? (
          <p className="text-xs text-gray-400">{t('common.loading', { defaultValue: 'Loading…' })}</p>
        ) : students.length === 0 ? (
          <p className="text-xs text-gray-400 py-4 text-center">
            {t('dashboard.courses.at_risk.empty', { defaultValue: 'No students currently flagged.' })}
          </p>
        ) : (
          <div className="space-y-2 border-t border-gray-100 pt-3">
            {students.map((s) => (
              <div key={s.user_id} className="bg-gray-50 rounded-lg p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-gray-900">
                    {`${s.first_name} ${s.last_name}`.trim() || s.username}
                    <span className="ms-1.5 font-normal text-gray-400">{s.email}</span>
                  </p>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      s.risk_level === 'high' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    {s.risk_level === 'high'
                      ? t('dashboard.courses.at_risk.high', { defaultValue: 'High risk' })
                      : t('dashboard.courses.at_risk.medium', { defaultValue: 'Medium risk' })}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {s.flags.map((flag) => (
                    <span
                      key={flag}
                      className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-200 text-gray-700"
                    >
                      {t(`dashboard.courses.at_risk.flag_${flag}`, { defaultValue: FLAG_LABELS[flag] })}
                    </span>
                  ))}
                </div>
                <p className="text-[11px] text-gray-500">
                  {t('dashboard.courses.at_risk.last_active', {
                    defaultValue: 'Last active {{when}}',
                    when: daysAgoLabel(s.days_since_activity),
                  })}
                  {' · '}
                  {t('dashboard.courses.at_risk.progress', {
                    defaultValue: '{{pct}}% complete',
                    pct: s.completion_percentage,
                  })}
                  {' · '}
                  {t('dashboard.courses.at_risk.failing_count', {
                    defaultValue: '{{count}} failing',
                    count: s.failing_assignments_count,
                  })}
                  {' · '}
                  {t('dashboard.courses.at_risk.missing_count', {
                    defaultValue: '{{count}} missing',
                    count: s.missing_assignments_count,
                  })}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
