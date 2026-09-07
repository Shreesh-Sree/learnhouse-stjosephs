'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getCourseGradebookExportUrl, importCourseRoster } from '@services/courses/courses'
import { Download, FileSpreadsheet, Upload } from 'lucide-react'
import React, { useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

type EditCourseRosterProps = {
    orgslug: string
}

/**
 * Two related bulk operations for onboarding/offboarding a semester's
 * students: a CSV roster upload that enrolls every email already
 * belonging to an org member (and invites everyone else to the org — see
 * the backend service's docstring for why course-level pending invites
 * aren't a thing here), and a gradebook CSV export for handing grades to
 * a registrar/SIS.
 */
export default function EditCourseRoster({ orgslug }: EditCourseRosterProps) {
    const { t } = useTranslation()
    const course = useCourse() as any
    const session = useLHSession() as any
    const access_token = session?.data?.tokens?.access_token
    const course_uuid = course?.courseStructure?.course_uuid

    const [file, setFile] = useState<File | null>(null)
    const [busy, setBusy] = useState(false)
    const [results, setResults] = useState<any[] | null>(null)
    const [exporting, setExporting] = useState(false)

    const handleImport = async () => {
        if (!file || !course_uuid || !access_token) return
        setBusy(true)
        setResults(null)
        try {
            const res = await importCourseRoster(course_uuid, file, access_token)
            if (res.success) {
                toast.success(res.data.message)
                setResults(res.data.results)
                setFile(null)
            } else {
                toast.error(res.data?.detail || t('common.something_went_wrong'))
            }
        } finally {
            setBusy(false)
        }
    }

    const handleExport = async () => {
        if (!course_uuid || !access_token) return
        setExporting(true)
        try {
            const resp = await fetch(getCourseGradebookExportUrl(course_uuid), {
                headers: { Authorization: `Bearer ${access_token}` },
            })
            if (!resp.ok) {
                toast.error(t('dashboard.courses.roster.export_error', { defaultValue: 'Could not export the gradebook.' }))
                return
            }
            const blob = await resp.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `gradebook-${course_uuid}.csv`
            document.body.appendChild(a)
            a.click()
            a.remove()
            URL.revokeObjectURL(url)
        } finally {
            setExporting(false)
        }
    }

    return (
        <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
            <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
                <div className="flex items-center gap-2">
                    <Upload size={16} className="text-gray-500" />
                    <p className="text-sm font-bold text-gray-900">
                        {t('dashboard.courses.roster.import_title', { defaultValue: 'Bulk-enroll from a CSV roster' })}
                    </p>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                    {t('dashboard.courses.roster.import_description', {
                        defaultValue: 'Upload a CSV with an "email" column (or a bare list of addresses, one per line). Students who already have an account in this organization are enrolled immediately; anyone else is invited to the organization — re-run this import once they’ve signed up.',
                    })}
                </p>
                <div className="flex items-center gap-2">
                    <input
                        type="file"
                        accept=".csv,text/csv"
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                        className="text-xs text-gray-600 file:me-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-gray-100 file:text-xs file:font-bold file:text-gray-700 hover:file:bg-gray-200"
                    />
                    <button
                        type="button"
                        onClick={handleImport}
                        disabled={!file || busy}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
                    >
                        {busy ? t('common.loading', { defaultValue: 'Loading…' }) : t('dashboard.courses.roster.import_button', { defaultValue: 'Import' })}
                    </button>
                </div>

                {results && (
                    <div className="mt-2 space-y-1 max-h-64 overflow-y-auto border-t border-gray-100 pt-3">
                        {results.map((r, i) => (
                            <div key={i} className="flex items-center justify-between text-xs">
                                <span className="text-gray-700">{r.email}</span>
                                <span
                                    className={`font-semibold px-2 py-0.5 rounded-full ${
                                        r.status === 'enrolled'
                                            ? 'bg-emerald-50 text-emerald-700'
                                            : r.status === 'invited_pending_signup'
                                                ? 'bg-amber-50 text-amber-700'
                                                : 'bg-gray-100 text-gray-500'
                                    }`}
                                >
                                    {r.status}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
                <div className="flex items-center gap-2">
                    <FileSpreadsheet size={16} className="text-gray-500" />
                    <p className="text-sm font-bold text-gray-900">
                        {t('dashboard.courses.roster.export_title', { defaultValue: 'Export gradebook' })}
                    </p>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                    {t('dashboard.courses.roster.export_description', {
                        defaultValue: 'Download a CSV with one row per enrolled student and one column per assignment — for a registrar or student information system.',
                    })}
                </p>
                <button
                    type="button"
                    onClick={handleExport}
                    disabled={exporting}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                    <Download size={13} />
                    {exporting ? t('common.loading', { defaultValue: 'Loading…' }) : t('dashboard.courses.roster.export_button', { defaultValue: 'Download CSV' })}
                </button>
            </div>
        </div>
    )
}
