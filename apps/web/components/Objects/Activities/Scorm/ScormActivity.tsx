'use client'
import React from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getScormContentUrl, getScormTracking, updateScormTracking } from '@services/courses/scorm'
import { ScormApi12, type ScormLessonStatus } from '@/lib/scorm/ScormApi12'

// Extends window without redeclaring the global type everywhere this file
// is imported from.
declare global {
  interface Window {
    API?: ScormApi12
  }
}

interface ScormActivityProps {
  activity: {
    activity_uuid: string
    content: {
      scorm_entry_point?: string
      scorm_title?: string
    }
  }
  course?: unknown
}

function ScormActivity({ activity }: ScormActivityProps) {
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const user = session?.data?.user

  const [status, setStatus] = React.useState<'loading' | 'ready' | 'error'>('loading')
  const iframeRef = React.useRef<HTMLIFrameElement | null>(null)
  const apiRef = React.useRef<ScormApi12 | null>(null)

  const entryPoint = activity?.content?.scorm_entry_point

  React.useEffect(() => {
    let cancelled = false

    async function init() {
      if (!access_token || !entryPoint) {
        setStatus('error')
        return
      }
      const res = await getScormTracking(activity.activity_uuid, access_token)
      if (cancelled) return

      const tracking = res?.data ?? {}
      const displayName =
        user?.first_name && user?.last_name
          ? `${user.first_name} ${user.last_name}`
          : user?.username ?? 'Learner'

      apiRef.current = new ScormApi12(
        {
          lesson_status: (tracking.lesson_status as ScormLessonStatus) ?? 'not_attempted',
          score_raw: tracking.score_raw ?? null,
          score_min: tracking.score_min ?? null,
          score_max: tracking.score_max ?? null,
          lesson_location: tracking.lesson_location ?? null,
          suspend_data: tracking.suspend_data ?? null,
          entry: tracking.lesson_status ? 'resume' : '',
          student_id: user?.user_uuid ?? '',
          student_name: displayName,
        },
        {
          onCommit: (data) => {
            // Fire-and-forget: SCORM content doesn't wait on LMSCommit's
            // return value beyond the synchronous "true"/"false" the shim
            // already returned. A failed background save just means this
            // particular commit doesn't persist — the SCO will commit again
            // on its own next save point.
            void updateScormTracking(activity.activity_uuid, data, access_token)
          },
        }
      )
      window.API = apiRef.current
      setStatus('ready')
    }

    init()
    return () => {
      cancelled = true
      delete window.API
      apiRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activity.activity_uuid, access_token, entryPoint])

  if (status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-gray-500">
        <AlertCircle size={28} className="text-rose-400" />
        <p className="text-sm">This SCORM package hasn't been set up yet.</p>
      </div>
    )
  }

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center py-16">
        <RefreshCw size={20} className="animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <iframe
      ref={iframeRef}
      src={getScormContentUrl(activity.activity_uuid, entryPoint as string)}
      title={activity?.content?.scorm_title || 'SCORM content'}
      className="w-full border-0 rounded-lg"
      style={{ minHeight: '70vh' }}
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
    />
  )
}

export default ScormActivity
