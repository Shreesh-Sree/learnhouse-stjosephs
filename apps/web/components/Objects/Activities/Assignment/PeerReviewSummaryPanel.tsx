'use client'
import React from 'react'
import { Star } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getPeerReviewSummaryForUser } from '@services/courses/assignments'

interface PeerReviewSummaryPanelProps {
  assignmentUuid: string
  userId: number
  accessToken: string
  enablePeerReview?: boolean
}

/**
 * Instructor-only reference view: every peer review a student received for
 * this assignment, with real reviewer identities and an average score.
 * Advisory only — nothing here writes to the student's grade; see the
 * backend module's docstring for why peer scores never bypass the
 * instructor's own grading action.
 */
export default function PeerReviewSummaryPanel({
  assignmentUuid,
  userId,
  accessToken,
  enablePeerReview,
}: PeerReviewSummaryPanelProps) {
  const { t } = useTranslation()
  const [summary, setSummary] = React.useState<any>(null)

  React.useEffect(() => {
    if (!enablePeerReview || !assignmentUuid || !userId || !accessToken) return
    let cancelled = false
    ;(async () => {
      const res = await getPeerReviewSummaryForUser(assignmentUuid, userId, accessToken)
      if (!cancelled && res.success) setSummary(res.data)
    })()
    return () => { cancelled = true }
  }, [enablePeerReview, assignmentUuid, userId, accessToken])

  if (!enablePeerReview || !summary || summary.total_count === 0) return null

  return (
    <div className="rounded-xl border nice-shadow bg-white border-gray-100 p-3 mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-gray-700">
          <Star size={14} className="text-amber-500" />
          <p className="text-xs font-bold">
            {t('dashboard.assignments.submissions.peer_review.title', { defaultValue: 'Peer review feedback' })}
          </p>
        </div>
        <p className="text-[11px] text-gray-400">
          {t('dashboard.assignments.submissions.peer_review.progress', {
            defaultValue: '{{done}}/{{total}} completed',
            done: summary.completed_count,
            total: summary.total_count,
          })}
          {summary.average_score !== null && (
            <span className="ms-2 font-bold text-gray-700">
              {t('dashboard.assignments.submissions.peer_review.average', {
                defaultValue: 'avg {{score}}/100',
                score: summary.average_score,
              })}
            </span>
          )}
        </p>
      </div>
      <div className="space-y-1.5">
        {summary.reviews.map((r: any) => (
          <div key={r.review_uuid} className="rounded-lg bg-gray-50 px-3 py-2 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-600">
                {t('dashboard.assignments.submissions.peer_review.reviewer_status', {
                  defaultValue: 'Reviewer (user #{{id}}) — {{status}}',
                  id: r.reviewer_user_id,
                  status: r.status,
                })}
              </span>
              {r.score !== null && r.score !== undefined && (
                <span className="font-bold text-gray-800">{r.score}/100</span>
              )}
            </div>
            {r.feedback && <p className="text-gray-600 mt-1">{r.feedback}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
