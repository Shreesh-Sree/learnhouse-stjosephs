'use client'
import React, { useState } from 'react'
import LearnHouseSpinner from '@components/Objects/Loaders/LearnHouseSpinner'
import ConfirmationModal from '@components/Objects/StyledElements/ConfirmationModal/ConfirmationModal'
import { ExternalLink, Package, Trash2, Upload } from 'lucide-react'
import { updateActivity } from '@services/courses/activities'
import { deleteScormPackage, getScormContentUrl, uploadScormPackage } from '@services/courses/scorm'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import toast from 'react-hot-toast'
import { mutate } from 'swr'
import ScormResultsTable from '@components/Objects/Activities/Scorm/ScormResultsTable'

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
  const [isRemovingPackage, setIsRemovingPackage] = useState(false)
  const [scormContent, setScormContent] = useState(activity?.content || {})
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)

  const currentEntryPoint = scormContent?.scorm_entry_point as string | undefined
  const currentTitle = scormContent?.scorm_title as string | undefined

  const invalidateCourseCaches = () => {
    mutate((key: string) => typeof key === 'string' && key.includes('/courses/org_slug/'))
  }

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
        setScormContent(res?.data?.content || {})
        invalidateCourseCaches()
      }
    } catch {
      toast.error('Failed to upload SCORM package', { id: toastId })
    } finally {
      setIsUploadingPackage(false)
    }
  }

  const handleRemovePackage = async () => {
    setIsRemovingPackage(true)
    const toastId = toast.loading('Removing SCORM package...')
    try {
      const res = await deleteScormPackage(activity.activity_uuid, access_token)
      if (res?.success === false) {
        toast.error('Failed to remove SCORM package', { id: toastId })
      } else {
        toast.success('SCORM package removed', { id: toastId })
        setScormContent(res?.data?.content || {})
        invalidateCourseCaches()
      }
    } catch {
      toast.error('Failed to remove SCORM package', { id: toastId })
    } finally {
      setIsRemovingPackage(false)
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
        invalidateCourseCaches()
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
              <span className="text-[11px] text-gray-400 truncate max-w-[180px]" title={currentEntryPoint}>
                {currentTitle || currentEntryPoint}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingPackage || isRemovingPackage}
              className="flex-1 inline-flex items-center justify-center gap-2 h-9 px-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
            >
              {isUploadingPackage ? <LearnHouseSpinner size={16} /> : <Upload size={15} />}
              {currentEntryPoint ? 'Replace package' : 'Upload package (.zip)'}
            </button>

            {currentEntryPoint && (
              <>
                <a
                  href={getScormContentUrl(activity.activity_uuid, currentEntryPoint)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Preview in a new tab"
                  className="inline-flex items-center justify-center h-9 w-9 flex-none text-gray-500 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <ExternalLink size={15} />
                </a>

                <ConfirmationModal
                  dialogTitle="Remove SCORM package?"
                  confirmationMessage="This deletes the uploaded package's files. Learner results already recorded for this activity are kept. You'll need to upload a package again before learners can open this activity."
                  confirmationButtonText="Remove package"
                  pendingButtonText="Removing..."
                  status="warning"
                  functionToExecute={handleRemovePackage}
                  dialogTrigger={
                    <button
                      type="button"
                      disabled={isUploadingPackage || isRemovingPackage}
                      title="Remove package"
                      className="inline-flex items-center justify-center h-9 w-9 flex-none text-rose-600 bg-rose-50 border border-rose-100 rounded-lg hover:bg-rose-100 transition-colors disabled:opacity-50"
                    >
                      <Trash2 size={15} />
                    </button>
                  }
                />
              </>
            )}
          </div>

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
        <p className="text-sm font-medium text-gray-700 mb-2">Learner results</p>
        <ScormResultsTable activityUuid={activity.activity_uuid} />
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
