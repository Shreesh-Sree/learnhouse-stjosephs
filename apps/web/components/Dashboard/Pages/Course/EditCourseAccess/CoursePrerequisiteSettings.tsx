'use client'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getOrgCourses, setCoursePrerequisite } from '@services/courses/courses'
import { GitBranch } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

type CoursePrerequisiteSettingsProps = {
  course_uuid: string
  orgslug: string
  prerequisite_course_id: number | null
}

/**
 * Learning-path prerequisite: this course requires another course in the
 * same org to be fully completed before a learner may self-enroll — see
 * apps/api's services/courses/courses.py:set_course_prerequisite and
 * services/trail/trail.py's enforcement at the enrollment endpoint.
 * Instructor-driven enrollment (bulk roster import) is a deliberate
 * override and ignores this.
 */
export default function CoursePrerequisiteSettings({
  course_uuid,
  orgslug,
  prerequisite_course_id,
}: CoursePrerequisiteSettingsProps) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token

  const [courses, setCourses] = useState<any[]>([])
  const [selected, setSelected] = useState<string>(prerequisite_course_id ? String(prerequisite_course_id) : '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setSelected(prerequisite_course_id ? String(prerequisite_course_id) : '')
  }, [prerequisite_course_id])

  useEffect(() => {
    if (!orgslug) return
    let stale = false
    ;(async () => {
      try {
        const res = await getOrgCourses(orgslug, null, access_token)
        if (!stale) setCourses(Array.isArray(res) ? res : [])
      } catch {
        // empty dropdown on failure
      }
    })()
    return () => {
      stale = true
    }
  }, [orgslug, access_token])

  const handleChange = async (raw: string) => {
    const nextId = raw ? parseInt(raw, 10) : null
    setSaving(true)
    try {
      await setCoursePrerequisite(course_uuid, nextId, access_token)
      setSelected(raw)
      toast.success(t('dashboard.courses.access.prerequisite.updated', { defaultValue: 'Prerequisite updated.' }))
    } catch {
      toast.error(t('common.something_went_wrong'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-6 bg-white rounded-xl nice-shadow p-5 space-y-2">
      <div className="flex items-center gap-2">
        <GitBranch size={16} className="text-gray-500" />
        <p className="text-sm font-bold text-gray-900">
          {t('dashboard.courses.access.prerequisite.title', { defaultValue: 'Prerequisite course' })}
        </p>
      </div>
      <p className="text-xs text-gray-500 leading-relaxed">
        {t('dashboard.courses.access.prerequisite.description', {
          defaultValue:
            'Learners must fully complete the selected course before they can self-enroll in this one. Does not affect bulk roster import, which is an explicit instructor override.',
        })}
      </p>
      <select
        value={selected}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
        className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none disabled:opacity-50"
      >
        <option value="">
          {t('dashboard.courses.access.prerequisite.none', { defaultValue: 'No prerequisite' })}
        </option>
        {courses
          .filter((c: any) => c.course_uuid !== course_uuid)
          .map((c: any) => (
            <option key={c.course_uuid} value={c.id}>
              {c.name}
            </option>
          ))}
      </select>
    </div>
  )
}
