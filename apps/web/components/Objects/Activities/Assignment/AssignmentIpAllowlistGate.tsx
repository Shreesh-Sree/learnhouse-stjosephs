'use client'
import React from 'react'
import { WifiOff, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { checkAssignmentIpAllowlistStatus } from '@services/courses/assignments'

interface AssignmentIpAllowlistGateProps {
  requireIpAllowlist: boolean
  assignmentUuid?: string | null
  accessToken?: string | null
  children: React.ReactNode
}

/**
 * Blocks the assignment view behind a "you're not on an allowed network"
 * screen when the assignment restricts submission to an IP allowlist and
 * this request's resolved client IP isn't in it. This is a UX courtesy
 * only — the real gate is server-side (every submission-mutating request
 * 403s from outside the allowlist; see _enforce_ip_allowlist_if_required in
 * the API's ip_allowlist service). A student who bypasses this screen
 * entirely still can't actually submit anything.
 *
 * Checked once per mount, with a manual recheck button, same as the SEB
 * gate this mirrors — the student's network position doesn't change
 * without them actually moving (e.g. onto campus Wi-Fi), which is exactly
 * the case the recheck button covers.
 */
export default function AssignmentIpAllowlistGate({
  requireIpAllowlist,
  assignmentUuid,
  accessToken,
  children,
}: AssignmentIpAllowlistGateProps) {
  const { t } = useTranslation()
  // null = not required or not yet checked, true = blocked, false = clear.
  const [isBlocked, setIsBlocked] = React.useState<boolean | null>(null)
  const [clientIp, setClientIp] = React.useState<string>('')
  const [isChecking, setIsChecking] = React.useState(false)

  const runCheck = React.useCallback(async () => {
    if (!requireIpAllowlist || !assignmentUuid || !accessToken) return
    setIsChecking(true)
    try {
      const { allowed, client_ip } = await checkAssignmentIpAllowlistStatus(assignmentUuid, accessToken)
      setIsBlocked(!allowed)
      setClientIp(client_ip || '')
    } catch (_error) {
      // A failed check is not proof of anything either way — the server-side
      // gate is what actually protects submissions, so fail OPEN here rather
      // than lock a student out of an assignment over a flaky network call.
      setIsBlocked(false)
    } finally {
      setIsChecking(false)
    }
  }, [requireIpAllowlist, assignmentUuid, accessToken])

  React.useEffect(() => {
    runCheck()
  }, [runCheck])

  if (!requireIpAllowlist || isBlocked !== true) {
    return <>{children}</>
  }

  return (
    <div className="max-w-2xl mx-auto my-16 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-8 text-center">
      <div className="mx-auto w-14 h-14 rounded-full bg-rose-50 flex items-center justify-center mb-4">
        <WifiOff className="text-rose-500" size={24} />
      </div>
      <h1 className="text-xl font-semibold text-gray-900 mb-2">
        {t('activities.ip_allowlist_gate.title', { defaultValue: 'This assignment can only be opened from an allowed network' })}
      </h1>
      <p className="text-sm text-gray-500 mb-6 leading-relaxed">
        {t('activities.ip_allowlist_gate.description', {
          defaultValue:
            "You'll need to connect from campus Wi-Fi or a lab computer to open this assignment. If you think this is a mistake, give your instructor or IT the address below.",
        })}
      </p>
      {clientIp && (
        <p className="text-xs font-mono text-gray-400 mb-6">
          {t('activities.ip_allowlist_gate.your_ip', { defaultValue: 'Your address: {{ip}}', ip: clientIp })}
        </p>
      )}
      <button
        type="button"
        onClick={runCheck}
        disabled={isChecking}
        className="inline-flex items-center gap-2 justify-center px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors disabled:opacity-50"
      >
        <RefreshCw size={14} className={isChecking ? 'animate-spin' : ''} />
        {t('activities.ip_allowlist_gate.check_again', { defaultValue: 'Check again' })}
      </button>
    </div>
  )
}
