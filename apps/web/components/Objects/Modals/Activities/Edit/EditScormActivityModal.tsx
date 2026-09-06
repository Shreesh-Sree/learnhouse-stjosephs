'use client'
import React, { useState } from 'react'
import dynamic from 'next/dynamic'
import LearnHouseSpinner from '@components/Objects/Loaders/LearnHouseSpinner'
import { Package, Upload } from 'lucide-react'
import { updateActivity } from '@services/courses/activities'
import { uploadScormPackage } from '@services/courses/scorm'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import toast from 'react-hot-toast'
import { mutate } from 'swr'

// EE component — dynamically imported so OSS builds (no ee/) degrade gracefully,
// mirroring how the activity page lazy-loads ScormActivity.
const ScormResults = dynamic(
  () => import('../../../../../ee/components/Activities/ScormResults'),
  { ssr: false },
)

interface EditScormActivityModalProps {
  activity: any
  courseUuid: string
  orgSlug: string
  onClose: () => void
}

function EditScormActivityModal({ activity, onClose }: EditScormActivityModalProps) {
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token

  const [name, setName] = useState(activity.name || '')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isUploadingPackage, setIsUploadingPackage] = useState(false)
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)
  const currentEntryPoint = activity?.content?.scorm_entry_point as string | undefined

  const handlePackageFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setIsUploadingPackage(true)
    const toastId = toast.loading('Uploading SCORM package...')
    try {
      const res = await uploadScormPackage(activity.activity_uuid, file, access_token)
      if (res?.success === false) {
        toast.error(res?.data?.detail || 'Failed to upload SCORM package', { id: toastId })
      } else {
        toast.success('SCORM package uploaded', { id: toastId })
        mutate((key: string) => typeof key === 'string' && key.includes('/courses/org_slug/'))
      }
    } catch {
      toast.error('Failed to upload SCORM package', { id: toastId })
    } finally {
      setIsUploadingPackage(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    const toastId = toast.loading('Updating SCORM activity...')
    try {
      const res = await updateActivity(
        { name },
        activity.activity_uuid,
        access_token,
      )

      if (res?.success === false) {
        toast.error('Failed to update SCORM activity', { id: toastId })
      } else {
        toast.success('SCORM activity updated', { id: toastId })
        mutate((key: string) => typeof key === 'string' && key.includes('/courses/org_slug/'))
        onClose()
      }
    } catch {
      toast.error('Failed to update SCORM activity', { id: toastId })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div
        className="relative flex items-center justify-center h-20 rounded-xl overflow-hidden"
        style={{
          backgroundImage:
            'repeating-linear-gradient(-45deg, transparent, transparent 6px, rgba(186,230,253,0.3) 6px, rgba(186,230,253,0.3) 7px)',
        }}
      >
        <span className="flex items-center gap-2 bg-white nice-shadow rounded-full px-4 py-1.5 text-sm font-medium text-gray-600">
          <Package size={18} className="text-sky-500" />
          SCORM Activity
        </span>
      </div>

      <div className="rounded-xl nice-shadow p-4 space-y-4">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700">SCORM package</label>
            {currentEntryPoint && (
              <span className="text-[11px] text-gray-400 truncate max-w-[200px]">{currentEntryPoint}</span>
            )}
          </div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploadingPackage}
            className="w-full inline-flex items-center justify-center gap-2 h-9 px-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            {isUploadingPackage ? (
              <LearnHouseSpinner size={16} />
            ) : (
              <Upload size={15} />
            )}
            {currentEntryPoint ? 'Replace package (.zip)' : 'Upload package (.zip)'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={handlePackageFileSelected}
          />
          <p className="text-[10px] text-gray-400">
            SCORM 1.2 packages only. Replacing an existing package overwrites it entirely.
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Activity name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            type="text"
            required
            placeholder="Enter a name..."
            className="w-full h-9 px-3 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors"
          />
        </div>
      </div>

      {/* Learner results (instructor reporting) */}
      <div className="rounded-xl nice-shadow p-4">
        <ScormResults activityUuid={activity.activity_uuid} />
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center justify-center h-9 px-5 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
        >
          {isSubmitting ? (
            <LearnHouseSpinner size={18} className="[&>div]:border-t-white" />
          ) : (
            'Save changes'
          )}
        </button>
      </div>
    </form>
  )
}

export default EditScormActivityModal
