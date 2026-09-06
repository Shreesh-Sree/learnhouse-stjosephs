'use client'
import React from 'react'
import { Lock, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { checkAssignmentSebStatus } from '@services/courses/assignments'

interface AssignmentSebGateProps {
  requireSafeExamBrowser: boolean
  assignmentUuid?: string | null
  accessToken?: string | null
  children: React.ReactNode
}

/**
 * Blocks the assignment view behind a "open this in Safe Exam Browser"
 * screen when the assignment requires it and this session doesn't look like
 * one. This is a UX courtesy only — the real gate is server-side (every
 * submission-mutating request 403s without a matching SEB session; see
 * _enforce_seb_if_required in the API's assignments service). A student who
 * bypasses this screen entirely still can't actually submit anything.
 *
 * Checked once per mount rather than polled: the student either already has
 * the .seb file (given to them by their instructor outside the app) and
 * loads this page from inside SEB, or they don't yet and need to go get it —
 * either way, nothing changes without a fresh navigation, which remounts
 * this component anyway. "Check again" covers the case where they open the
 * config and come back to this same browser tab instead of a fresh SEB
 * window.
 */
export default function AssignmentSebGate({
  requireSafeExamBrowser,
  assignmentUuid,
  accessToken,
  children,
}: AssignmentSebGateProps) {
  const { t } = useTranslation()
  // null = not required or not yet checked, true = blocked, false = clear.
  const [isBlocked, setIsBlocked] = React.useState<boolean | null>(null)
  const [isChecking, setIsChecking] = React.useState(false)

  const runCheck = React.useCallback(async () => {
    if (!requireSafeExamBrowser || !assignmentUuid || !accessToken) return
    setIsChecking(true)
    try {
      const { seb_ok } = await checkAssignmentSebStatus(assignmentUuid, accessToken)
      setIsBlocked(!seb_ok)
    } catch (_error) {
      // A failed check is not proof of anything either way — the server-side
      // gate is what actually protects submissions, so fail OPEN here rather
      // than lock a student out of an assignment over a flaky network call.
      setIsBlocked(false)
    } finally {
      setIsChecking(false)
    }
  }, [requireSafeExamBrowser, assignmentUuid, accessToken])

  React.useEffect(() => {
    runCheck()
  }, [runCheck])

  if (!requireSafeExamBrowser || isBlocked !== true) {
    return <>{children}</>
  }

  return (
    <div className="max-w-2xl mx-auto my-16 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-8 text-center">
      <div className="mx-auto w-14 h-14 rounded-full bg-rose-50 flex items-center justify-center mb-4">
        <Lock className="text-rose-500" size={24} />
      </div>
      <h1 className="text-xl font-semibold text-gray-900 mb-2">
        {t('activities.seb_gate.title', { defaultValue: 'This assignment requires Safe Exam Browser' })}
      </h1>
      <p className="text-sm text-gray-500 mb-6 leading-relaxed">
        {t('activities.seb_gate.description', {
          defaultValue:
            "You can't open this assignment from a regular browser. Ask your instructor for the exam config file (.seb), install Safe Exam Browser if you haven't already, and open the assignment from inside it.",
        })}
      </p>
      <button
        type="button"
        onClick={runCheck}
        disabled={isChecking}
        className="inline-flex items-center gap-2 justify-center px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors disabled:opacity-50"
      >
        <RefreshCw size={14} className={isChecking ? 'animate-spin' : ''} />
        {t('activities.seb_gate.check_again', { defaultValue: 'Check again' })}
      </button>
    </div>
  )
}
