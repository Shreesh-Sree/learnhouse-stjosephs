'use client'
import React from 'react'
import { Star, X, Send, CheckCircle2, Hourglass } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import {
  getMyPeerReviewsReceived,
  getMyPeerReviewsToDo,
  getPeerReviewSubmissionView,
  submitPeerReview,
} from '@services/courses/assignments'

interface AssignmentPeerReviewPanelProps {
  assignmentUuid?: string | null
  enablePeerReview: boolean
  accessToken?: string | null
}

interface ReviewRow {
  review_uuid: string
  score: number | null
  feedback: string | null
  status: 'PENDING' | 'COMPLETED'
}

// Best-effort, type-agnostic rendering of a task's submitted answer. Real
// polish would mean reusing each TaskXxxObject component in a dedicated
// read-only "peer review" view mode — out of scope here; this is enough for
// a reviewer to actually read and judge the work.
function renderAnswer(taskSubmission: any): string {
  if (taskSubmission === null || taskSubmission === undefined) return '(no answer submitted)'
  if (typeof taskSubmission === 'string') return taskSubmission
  if (typeof taskSubmission === 'number') return String(taskSubmission)
  try {
    return JSON.stringify(taskSubmission, null, 2)
  } catch {
    return String(taskSubmission)
  }
}

/**
 * Peer review for a student: a "to review" queue (each entry opens the
 * target's submission, anonymized, for scoring + written feedback) and a
 * "received" section showing feedback about the caller's own submission —
 * withheld until every review of it is complete, and never showing who
 * wrote it. See the backend module docstring for why both directions are
 * hard-coded anonymous rather than configurable.
 */
export default function AssignmentPeerReviewPanel({
  assignmentUuid,
  enablePeerReview,
  accessToken,
}: AssignmentPeerReviewPanelProps) {
  const { t } = useTranslation()
  const [toDo, setToDo] = React.useState<ReviewRow[] | null>(null)
  const [received, setReceived] = React.useState<any>(null)
  const [activeReview, setActiveReview] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    if (!enablePeerReview || !assignmentUuid || !accessToken) return
    const [toDoRes, receivedRes] = await Promise.all([
      getMyPeerReviewsToDo(assignmentUuid, accessToken),
      getMyPeerReviewsReceived(assignmentUuid, accessToken),
    ])
    if (toDoRes.success) setToDo(toDoRes.data)
    if (receivedRes.success) setReceived(receivedRes.data)
  }, [enablePeerReview, assignmentUuid, accessToken])

  React.useEffect(() => {
    load()
  }, [load])

  if (!enablePeerReview) return null

  return (
    <div className="rounded-2xl border border-gray-200/80 bg-white nice-shadow p-5 mb-5">
      <div className="flex items-center gap-2 mb-3">
        <Star size={16} className="text-amber-500" />
        <p className="text-sm font-bold text-gray-900">
          {t('activities.peer_review_panel.title', { defaultValue: 'Peer review' })}
        </p>
      </div>

      <div className="space-y-1.5 mb-4">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
          {t('activities.peer_review_panel.to_review', { defaultValue: 'Assigned to you' })}
        </p>
        {!toDo || toDo.length === 0 ? (
          <p className="text-[11px] text-gray-400">
            {t('activities.peer_review_panel.none_yet', { defaultValue: 'Nothing assigned yet.' })}
          </p>
        ) : (
          toDo.map((review, idx) => (
            <div key={review.review_uuid} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2">
              <div className="flex items-center gap-2">
                {review.status === 'COMPLETED' ? (
                  <CheckCircle2 size={13} className="text-emerald-500" />
                ) : (
                  <Hourglass size={13} className="text-amber-500" />
                )}
                <p className="text-xs font-semibold text-gray-800">
                  {t('activities.peer_review_panel.submission_label', { defaultValue: 'Submission #{{n}}', n: idx + 1 })}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveReview(review.review_uuid)}
                className="px-2.5 py-1 text-[11px] font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200/80 transition-colors"
              >
                {review.status === 'COMPLETED'
                  ? t('activities.peer_review_panel.view', { defaultValue: 'View' })
                  : t('activities.peer_review_panel.review', { defaultValue: 'Review' })}
              </button>
            </div>
          ))
        )}
      </div>

      <div className="space-y-1.5">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
          {t('activities.peer_review_panel.received', { defaultValue: 'Feedback received' })}
        </p>
        {!received || !received.revealed ? (
          <p className="text-[11px] text-gray-400">
            {t('activities.peer_review_panel.not_revealed', {
              defaultValue: '{{done}} of {{total}} reviews done — feedback appears once all are in.',
              done: received?.completed_count ?? 0,
              total: received?.total_count ?? 0,
            })}
          </p>
        ) : (
          received.reviews.map((r: ReviewRow, idx: number) => (
            <div key={r.review_uuid} className="rounded-lg bg-amber-50/60 px-3 py-2">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-bold text-amber-900">
                  {t('activities.peer_review_panel.reviewer_label', { defaultValue: 'Reviewer #{{n}}', n: idx + 1 })}
                </p>
                {r.score !== null && (
                  <p className="text-xs font-bold text-amber-700">{r.score}/100</p>
                )}
              </div>
              {r.feedback && <p className="text-[11px] text-amber-800 mt-1">{r.feedback}</p>}
            </div>
          ))
        )}
      </div>

      {activeReview && (
        <PeerReviewModal
          assignmentUuid={assignmentUuid!}
          reviewUuid={activeReview}
          accessToken={accessToken!}
          onClose={() => setActiveReview(null)}
          onSubmitted={() => {
            setActiveReview(null)
            load()
          }}
        />
      )}
    </div>
  )
}

function PeerReviewModal({
  assignmentUuid,
  reviewUuid,
  accessToken,
  onClose,
  onSubmitted,
}: {
  assignmentUuid: string
  reviewUuid: string
  accessToken: string
  onClose: () => void
  onSubmitted: () => void
}) {
  const { t } = useTranslation()
  const [data, setData] = React.useState<any>(null)
  const [score, setScore] = React.useState<string>('')
  const [feedback, setFeedback] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    ;(async () => {
      const res = await getPeerReviewSubmissionView(assignmentUuid, reviewUuid, accessToken)
      if (cancelled) return
      if (res.success) {
        setData(res.data)
        setScore(res.data.score !== null && res.data.score !== undefined ? String(res.data.score) : '')
        setFeedback(res.data.feedback || '')
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    })()
    return () => { cancelled = true }
  }, [assignmentUuid, reviewUuid, accessToken, t])

  const isCompleted = data?.status === 'COMPLETED'

  const handleSubmit = async () => {
    setBusy(true)
    try {
      const parsedScore = score.trim() === '' ? null : Math.max(0, Math.min(100, Number(score)))
      const res = await submitPeerReview(assignmentUuid, reviewUuid, parsedScore, feedback || null, accessToken)
      if (res.success) {
        toast.success(t('activities.peer_review_panel.submitted', { defaultValue: 'Review submitted.' }))
        onSubmitted()
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6" onClick={onClose}>
      <div
        className="bg-white rounded-2xl max-w-xl w-full max-h-[80vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-bold text-gray-900">
            {t('activities.peer_review_panel.modal_title', { defaultValue: 'Review this submission' })}
          </p>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        {!data ? (
          <p className="text-xs text-gray-400">{t('common.loading', { defaultValue: 'Loading…' })}</p>
        ) : (
          <div className="space-y-4">
            {data.tasks.map((task: any) => (
              <div key={task.assignment_task_uuid} className="rounded-lg border border-gray-100 p-3">
                <p className="text-xs font-bold text-gray-900">{task.title}</p>
                {task.description && <p className="text-[11px] text-gray-500 mt-0.5">{task.description}</p>}
                <pre className="text-[11px] text-gray-700 bg-gray-50 rounded-md p-2 mt-2 whitespace-pre-wrap break-words">
                  {renderAnswer(task.task_submission)}
                </pre>
              </div>
            ))}

            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-gray-700">
                {t('activities.peer_review_panel.score_label', { defaultValue: 'Score (0-100, optional)' })}
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={score}
                disabled={isCompleted}
                onChange={(e) => setScore(e.target.value)}
                className="w-24 px-3 py-1.5 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none disabled:opacity-50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-gray-700">
                {t('activities.peer_review_panel.feedback_label', { defaultValue: 'Written feedback' })}
              </label>
              <textarea
                value={feedback}
                disabled={isCompleted}
                onChange={(e) => setFeedback(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none disabled:opacity-50 resize-none"
              />
            </div>

            {!isCompleted && (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={busy}
                className="w-full inline-flex items-center justify-center gap-2 h-9 px-4 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors disabled:opacity-50"
              >
                <Send size={14} />
                {t('activities.peer_review_panel.submit_review', { defaultValue: 'Submit review' })}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
