'use client'
import React from 'react'
import { Clock, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import toast from 'react-hot-toast'
import { useAssignmentSubmission } from '@components/Contexts/Assignments/AssignmentSubmissionContext'
import { startAssignmentAttempt } from '@services/courses/assignments'
import { parseDueDate } from './AssignmentStudentActivity'

const DONE_STATUSES = new Set(['SUBMITTED', 'GRADED', 'LATE'])

interface AssignmentTimeLimitGateProps {
  assignmentUuid: string
  timeLimitMinutes?: number | null
  accessToken?: string | null
  children: React.ReactNode
}

/**
 * Blocks the assignment's task editors behind an explicit "Start attempt"
 * action when a time limit is set, then shows a live countdown once started.
 *
 * Deliberately does NOT auto-start on mount — a student opening the page
 * shouldn't have the clock start without a conscious choice, same reasoning
 * as every real timed-exam tool (Moodle, Canvas). The countdown here is a
 * courtesy display; the real enforcement is server-side
 * (_enforce_time_limit_if_set in the assignments service), same trust model
 * as the SEB gate right next to this one in activity.tsx.
 */
export default function AssignmentTimeLimitGate({
  assignmentUuid,
  timeLimitMinutes,
  accessToken,
  children,
}: AssignmentTimeLimitGateProps) {
  const submission = useAssignmentSubmission() as any
  const queryClient = useQueryClient()
  const [isStarting, setIsStarting] = React.useState(false)

  if (!timeLimitMinutes) {
    return <>{children}</>
  }

  // Already submitted/graded — nothing left to gate or count down; the rest
  // of the app already renders the submitted/read-only view for this state.
  if (submission?.submission_status && DONE_STATUSES.has(submission.submission_status)) {
    return <>{children}</>
  }

  if (!submission?.started_at) {
    const handleStart = async () => {
      if (!accessToken || isStarting) return
      setIsStarting(true)
      try {
        const res = await startAssignmentAttempt(assignmentUuid, accessToken)
        if (res?.success === false) {
          toast.error(res?.data?.detail || "Couldn't start the attempt.")
          return
        }
        queryClient.invalidateQueries({ queryKey: queryKeys.assignments.submission(assignmentUuid) })
      } catch (_error) {
        toast.error("Couldn't start the attempt.")
      } finally {
        setIsStarting(false)
      }
    }

    const plural = timeLimitMinutes === 1 ? '' : 's'
    return (
      <div className="max-w-lg mx-auto my-16 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-8 text-center">
        <div className="mx-auto w-14 h-14 rounded-full bg-amber-50 flex items-center justify-center mb-4">
          <Clock className="text-amber-500" size={24} />
        </div>
        <h1 className="text-xl font-semibold text-gray-900 mb-2">Timed assignment</h1>
        <p className="text-sm text-gray-500 mb-6 leading-relaxed">
          Once you start, you&apos;ll have {timeLimitMinutes} minute{plural} to finish and submit.
          The clock keeps running even if you close this page.
        </p>
        <button
          type="button"
          onClick={handleStart}
          disabled={isStarting}
          className="inline-flex items-center gap-2 justify-center px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors disabled:opacity-50"
        >
          {isStarting && <RefreshCw size={14} className="animate-spin" />}
          Start attempt
        </button>
      </div>
    )
  }

  return (
    <>
      <TimeLimitBanner startedAt={submission.started_at} timeLimitMinutes={timeLimitMinutes} />
      {children}
    </>
  )
}

function computeRemainingMs(startedAt: string, timeLimitMinutes: number): number {
  const parsed = parseDueDate(startedAt)
  if (!parsed) return timeLimitMinutes * 60_000 // unparseable start time: don't falsely show "time's up"
  return parsed.at.getTime() + timeLimitMinutes * 60_000 - Date.now()
}

function TimeLimitBanner({
  startedAt,
  timeLimitMinutes,
}: {
  startedAt: string
  timeLimitMinutes: number
}) {
  const [remainingMs, setRemainingMs] = React.useState(() => computeRemainingMs(startedAt, timeLimitMinutes))

  React.useEffect(() => {
    const id = setInterval(() => {
      setRemainingMs(computeRemainingMs(startedAt, timeLimitMinutes))
    }, 1000)
    return () => clearInterval(id)
  }, [startedAt, timeLimitMinutes])

  const isLow = remainingMs < 5 * 60_000
  const clamped = Math.max(0, remainingMs)
  const minutes = Math.floor(clamped / 60_000)
  const seconds = Math.floor((clamped % 60_000) / 1000)

  return (
    <div
      className={`mb-3 flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold ${
        isLow ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'
      }`}
    >
      <Clock size={14} />
      {remainingMs > 0
        ? `Time remaining: ${minutes}:${String(seconds).padStart(2, '0')}`
        : 'Time is up — submitting your answers now'}
    </div>
  )
}
