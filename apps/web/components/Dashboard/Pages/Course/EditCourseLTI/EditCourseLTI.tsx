'use client'
import { useCourse } from '@components/Contexts/CourseContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import {
  LTILink,
  LTILinkCreated,
  createCourseLTILink,
  getCourseLTILinks,
  revokeCourseLTILink,
} from '@services/courses/lti'
import { Check, Copy, Link2, Trash2 } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'

type EditCourseLTIProps = {
  orgslug: string
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard unavailable — the value is still selectable in the input
    }
  }
  return (
    <div className="space-y-1">
      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
      <div className="flex items-center gap-2">
        <input
          readOnly
          value={value}
          onFocus={(e) => e.target.select()}
          className="flex-1 text-xs font-mono bg-gray-50 border border-gray-200 rounded-md px-2 py-1.5 text-gray-700"
        />
        <button
          type="button"
          onClick={copy}
          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500"
          aria-label="Copy"
        >
          {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  )
}

/**
 * LTI 1.1 tool-provider links for this course — see apps/api's
 * db/lti.py module docstring for the scope decision (Tool Provider only,
 * LTI 1.1 not the newer 1.3/Advantage spec). Each link is its own
 * consumer_key/secret pair bound to exactly this course; paste the three
 * values shown right after creation into the external LMS's LTI tool
 * configuration (the secret is shown only once).
 */
export default function EditCourseLTI({ orgslug }: EditCourseLTIProps) {
  const { t } = useTranslation()
  const course = useCourse() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const course_uuid = course?.courseStructure?.course_uuid

  const [links, setLinks] = useState<LTILink[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [label, setLabel] = useState('')
  const [justCreated, setJustCreated] = useState<LTILinkCreated | null>(null)

  useEffect(() => {
    if (!course_uuid) return
    let stale = false
    ;(async () => {
      setLoading(true)
      try {
        const res = await getCourseLTILinks(course_uuid, access_token)
        if (!stale) setLinks(res || [])
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

  const handleCreate = async () => {
    if (!course_uuid) return
    setCreating(true)
    try {
      const created = await createCourseLTILink(course_uuid, label.trim() || null, access_token)
      setJustCreated(created)
      setLabel('')
      const res = await getCourseLTILinks(course_uuid, access_token)
      setLinks(res || [])
    } catch (err: any) {
      toast.error(err?.message || t('common.something_went_wrong'))
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (link_uuid: string) => {
    if (!course_uuid) return
    try {
      await revokeCourseLTILink(course_uuid, link_uuid, access_token)
      setLinks((prev) => prev.map((l) => (l.link_uuid === link_uuid ? { ...l, is_active: false } : l)))
    } catch {
      toast.error(t('common.something_went_wrong'))
    }
  }

  return (
    <div className="ps-4 pe-4 sm:ps-10 sm:pe-10 py-6 space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl nice-shadow p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Link2 size={16} className="text-gray-500" />
          <p className="text-sm font-bold text-gray-900">
            {t('dashboard.courses.lti.title', { defaultValue: 'LTI 1.1 links' })}
          </p>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed">
          {t('dashboard.courses.lti.description', {
            defaultValue:
              'Let another LMS (Canvas, Moodle, Blackboard, ...) launch into this course. Create a link, then paste its launch URL, consumer key and secret into that LMS\'s LTI tool configuration. A student launched this way gets a LearnHouse account automatically if they don\'t already have one.',
          })}
        </p>

        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder={t('dashboard.courses.lti.label_placeholder', { defaultValue: 'Label (optional, e.g. "Fall 2026 Canvas")' })}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {creating ? t('common.loading', { defaultValue: 'Loading…' }) : t('dashboard.courses.lti.create_button', { defaultValue: 'Create link' })}
          </button>
        </div>

        {justCreated && (
          <div className="mt-2 p-4 bg-amber-50 border border-amber-200 rounded-lg space-y-3">
            <p className="text-xs font-semibold text-amber-800">
              {t('dashboard.courses.lti.secret_warning', {
                defaultValue: 'This secret is shown only once — copy it now.',
              })}
            </p>
            <CopyField label={t('dashboard.courses.lti.launch_url', { defaultValue: 'Launch URL' })} value={justCreated.launch_url} />
            <CopyField label={t('dashboard.courses.lti.consumer_key', { defaultValue: 'Consumer key' })} value={justCreated.consumer_key} />
            <CopyField label={t('dashboard.courses.lti.consumer_secret', { defaultValue: 'Consumer secret' })} value={justCreated.consumer_secret} />
          </div>
        )}

        {!loading && links.length > 0 && (
          <div className="mt-2 space-y-2 border-t border-gray-100 pt-3">
            {links.map((link) => (
              <div key={link.link_uuid} className="flex items-center justify-between text-xs py-1.5">
                <div>
                  <span className="font-semibold text-gray-800">
                    {link.label || t('dashboard.courses.lti.unlabeled', { defaultValue: 'Unlabeled link' })}
                  </span>
                  <span
                    className={`ms-2 font-semibold px-2 py-0.5 rounded-full ${
                      link.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {link.is_active
                      ? t('dashboard.courses.lti.active', { defaultValue: 'Active' })
                      : t('dashboard.courses.lti.revoked', { defaultValue: 'Revoked' })}
                  </span>
                </div>
                {link.is_active && (
                  <button
                    type="button"
                    onClick={() => handleRevoke(link.link_uuid)}
                    className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600"
                    aria-label="Revoke"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
