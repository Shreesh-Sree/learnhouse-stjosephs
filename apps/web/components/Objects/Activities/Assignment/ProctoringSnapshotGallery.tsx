'use client'
import React from 'react'
import { Camera, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  deleteProctoringSnapshots,
  getProctoringSnapshotUrl,
  getProctoringSnapshots,
} from '@services/courses/assignments'
import ConfirmationModal from '@components/Objects/StyledElements/ConfirmationModal/ConfirmationModal'
import { useTranslation } from 'react-i18next'

interface ProctoringSnapshotGalleryProps {
  assignmentUuid: string
  userId: number
  accessToken: string
  requireWebcamProctoring?: boolean
}

interface SnapshotEntry {
  snapshot_uuid: string
  captured_at: string
  objectUrl: string
}

/**
 * The serve endpoint requires a Bearer token, so a plain `<img src>` can't
 * carry auth — each snapshot is fetched with `fetch` and turned into a
 * local object URL instead.
 */
export default function ProctoringSnapshotGallery({
  assignmentUuid,
  userId,
  accessToken,
  requireWebcamProctoring,
}: ProctoringSnapshotGalleryProps) {
  const { t } = useTranslation()
  const [snapshots, setSnapshots] = React.useState<SnapshotEntry[] | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [preview, setPreview] = React.useState<string | null>(null)
  const objectUrlsRef = React.useRef<string[]>([])

  const revokeAll = React.useCallback(() => {
    objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    objectUrlsRef.current = []
  }, [])

  const load = React.useCallback(async () => {
    if (!assignmentUuid || !userId || !accessToken) return
    setLoading(true)
    try {
      const res = await getProctoringSnapshots(assignmentUuid, userId, accessToken)
      if (!res.success || !Array.isArray(res.data)) {
        setSnapshots([])
        return
      }
      revokeAll()
      const entries: SnapshotEntry[] = []
      for (const row of res.data) {
        try {
          const fileRes = await fetch(getProctoringSnapshotUrl(assignmentUuid, row.snapshot_uuid), {
            headers: { Authorization: `Bearer ${accessToken}` },
          })
          if (!fileRes.ok) continue
          const blob = await fileRes.blob()
          const objectUrl = URL.createObjectURL(blob)
          objectUrlsRef.current.push(objectUrl)
          entries.push({
            snapshot_uuid: row.snapshot_uuid,
            captured_at: row.captured_at,
            objectUrl,
          })
        } catch (_error) {
          // Skip a single bad file rather than failing the whole gallery.
        }
      }
      setSnapshots(entries)
    } finally {
      setLoading(false)
    }
  }, [assignmentUuid, userId, accessToken, revokeAll])

  React.useEffect(() => {
    if (requireWebcamProctoring) load()
    return () => revokeAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignmentUuid, userId, requireWebcamProctoring])

  const handleDeleteAll = async () => {
    const res = await deleteProctoringSnapshots(assignmentUuid, userId, accessToken)
    if (res.success) {
      toast.success(
        t('dashboard.assignments.submissions.proctoring.delete_success', {
          defaultValue: 'Snapshots deleted.',
        })
      )
      revokeAll()
      setSnapshots([])
    } else {
      toast.error(res.data?.detail || t('common.something_went_wrong'))
    }
  }

  if (!requireWebcamProctoring) return null

  return (
    <div className="rounded-xl border nice-shadow bg-white border-gray-100 p-3 mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-gray-700">
          <Camera size={14} />
          <p className="text-xs font-bold">
            {t('dashboard.assignments.submissions.proctoring.title', { defaultValue: 'Webcam proctoring snapshots' })}
          </p>
        </div>
        {snapshots && snapshots.length > 0 && (
          <ConfirmationModal
            confirmationButtonText={t('dashboard.assignments.submissions.proctoring.delete_all', { defaultValue: 'Delete all' })}
            confirmationMessage={t('dashboard.assignments.submissions.proctoring.delete_confirm', {
              defaultValue: 'This permanently deletes every captured snapshot for this student on this assignment.',
            })}
            dialogTitle={t('dashboard.assignments.submissions.proctoring.delete_all', { defaultValue: 'Delete all' })}
            functionToExecute={handleDeleteAll}
            status="warning"
            dialogTrigger={
              <button className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-rose-700 bg-rose-50 rounded-lg hover:bg-rose-100/80 transition-colors cursor-pointer">
                <Trash2 size={11} />
                <span>{t('dashboard.assignments.submissions.proctoring.delete_all', { defaultValue: 'Delete all' })}</span>
              </button>
            }
          />
        )}
      </div>

      {loading && (
        <p className="text-[11px] text-gray-400">
          {t('dashboard.assignments.submissions.proctoring.loading', { defaultValue: 'Loading snapshots…' })}
        </p>
      )}

      {!loading && snapshots && snapshots.length === 0 && (
        <p className="text-[11px] text-gray-400">
          {t('dashboard.assignments.submissions.proctoring.empty', {
            defaultValue: 'No snapshots captured — the student may have declined the camera prompt.',
          })}
        </p>
      )}

      {!loading && snapshots && snapshots.length > 0 && (
        <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
          {snapshots.map((snap) => (
            <button
              key={snap.snapshot_uuid}
              type="button"
              onClick={() => setPreview(snap.objectUrl)}
              className="relative aspect-video rounded-md overflow-hidden bg-gray-100 border border-gray-200 hover:ring-2 hover:ring-gray-300 transition-all"
              title={snap.captured_at}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={snap.objectUrl} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8"
          onClick={() => setPreview(null)}
        >
          <button
            type="button"
            onClick={() => setPreview(null)}
            className="absolute top-4 right-4 text-white/80 hover:text-white"
          >
            <X size={20} />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt="" className="max-h-full max-w-full rounded-lg" />
        </div>
      )}
    </div>
  )
}
