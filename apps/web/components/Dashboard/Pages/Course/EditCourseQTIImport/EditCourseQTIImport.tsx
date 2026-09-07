'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { importQTIQuestionBank, QTIImportResult } from '@services/courses/qti'
import { FileUp, Upload } from 'lucide-react'
import React, { useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

type EditCourseQTIImportProps = {
  orgslug: string
}

/**
 * QTI 1.2 question-bank import — see apps/api's
 * services/courses/qti_import.py module docstring for the scope decision
 * (QTI 1.2 only, multiple-choice/true-false only). A successful import
 * creates ONE NEW activity in the chosen chapter holding every parsed
 * question as a quiz block, which the instructor can then review, edit,
 * reorder, and publish like any other quiz.
 */
export default function EditCourseQTIImport({ orgslug }: EditCourseQTIImportProps) {
  const { t } = useTranslation()
  const course = useCourse() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const course_uuid = course?.courseStructure?.course_uuid
  const chapters = course?.courseStructure?.chapters || []

  const [chapterId, setChapterId] = useState<string>('')
  const [activityName, setActivityName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<QTIImportResult | null>(null)

  const handleImport = async () => {
    if (!file || !course_uuid || !chapterId) return
    setBusy(true)
    setResult(null)
    try {
      const res = await importQTIQuestionBank(
        course_uuid,
        parseInt(chapterId, 10),
        activityName.trim() || null,
        file,
        access_token
      )
      if (res.success) {
        setResult(res.data)
        toast.success(
          t('dashboard.courses.qti.import_success', {
            defaultValue: '{{count}} question(s) imported.',
            count: res.data.questions_imported,
          })
        )
        setFile(null)
        setActivityName('')
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
        <div className="flex items-center gap-2">
          <FileUp size={16} className="text-gray-500" />
          <p className="text-sm font-bold text-gray-900">
            {t('dashboard.courses.qti.title', { defaultValue: 'Import a QTI question bank' })}
          </p>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed">
          {t('dashboard.courses.qti.description', {
            defaultValue:
              'Upload a QTI 1.2 file (or a zip of several) exported from another quiz tool. Multiple-choice and true/false questions are imported as a new quiz activity in the chapter you pick; unsupported item types (essay, short answer, matching, ...) are reported and skipped rather than guessed at.',
          })}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <select
            value={chapterId}
            onChange={(e) => setChapterId(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">
              {t('dashboard.courses.qti.pick_chapter', { defaultValue: 'Choose a chapter…' })}
            </option>
            {chapters.map((ch: any) => (
              <option key={ch.id} value={ch.id}>
                {ch.name}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder={t('dashboard.courses.qti.activity_name_placeholder', {
              defaultValue: 'Activity name (optional)',
            })}
            value={activityName}
            onChange={(e) => setActivityName(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="file"
            accept=".xml,.zip,application/xml,text/xml,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-xs text-gray-600 file:me-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-gray-100 file:text-xs file:font-bold file:text-gray-700 hover:file:bg-gray-200"
          />
          <button
            type="button"
            onClick={handleImport}
            disabled={!file || !chapterId || busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            <Upload size={13} />
            {busy ? t('common.loading', { defaultValue: 'Loading…' }) : t('dashboard.courses.qti.import_button', { defaultValue: 'Import' })}
          </button>
        </div>

        {result && (
          <div className="mt-2 space-y-2 border-t border-gray-100 pt-3">
            <p className="text-xs font-semibold text-emerald-700">
              {t('dashboard.courses.qti.imported_count', {
                defaultValue: '{{count}} question(s) imported into a new activity.',
                count: result.questions_imported,
              })}
            </p>
            {result.questions_skipped.length > 0 && (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                <p className="text-xs font-semibold text-amber-700">
                  {t('dashboard.courses.qti.skipped_count', {
                    defaultValue: '{{count}} item(s) skipped:',
                    count: result.questions_skipped.length,
                  })}
                </p>
                {result.questions_skipped.map((s, i) => (
                  <div key={i} className="text-xs text-gray-500">
                    <span className="font-mono">{s.identifier}</span> — {s.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
