'use client'
import React from 'react'
import { Users, LogOut, Send, Plus, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import {
  createAssignmentGroup,
  getAssignmentGroups,
  joinAssignmentGroup,
  leaveAssignmentGroup,
  submitAssignmentGroupForGrading,
} from '@services/courses/assignments'
import ConfirmationModal from '@components/Objects/StyledElements/ConfirmationModal/ConfirmationModal'

interface AssignmentGroupPanelProps {
  assignmentUuid?: string | null
  allowGroupSubmission: boolean
  groupMinSize?: number | null
  groupMaxSize?: number | null
  accessToken?: string | null
}

interface GroupRow {
  group_uuid: string
  name: string
  member_count: number
  is_full: boolean
  members: { user_id: number }[] | null
}

/**
 * Team formation for a group-submission assignment: create/join/leave a
 * team, and — once in one — a single "Submit for the whole team" action
 * that syncs everyone's answers and hands the assignment in for every
 * member at once (see the backend's submit_group_assignment). Every
 * member's grade/submission still lives in their own individual row under
 * the hood (see db.courses.assignment_groups' module docstring) — this
 * panel is the only place that makes it feel like one shared hand-in.
 *
 * Deliberately NOT a blocking gate like AssignmentSebGate/
 * AssignmentTimeLimitGate: a student can still work through tasks solo
 * (autosaving to their own row) before joining a team, so this renders
 * alongside the assignment content rather than hiding it.
 */
export default function AssignmentGroupPanel({
  assignmentUuid,
  allowGroupSubmission,
  groupMinSize,
  groupMaxSize,
  accessToken,
}: AssignmentGroupPanelProps) {
  const { t } = useTranslation()
  const [groups, setGroups] = React.useState<GroupRow[] | null>(null)
  const [newGroupName, setNewGroupName] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  const load = React.useCallback(async () => {
    if (!allowGroupSubmission || !assignmentUuid || !accessToken) return
    const res = await getAssignmentGroups(assignmentUuid, accessToken)
    if (res.success && Array.isArray(res.data)) {
      setGroups(res.data)
    }
  }, [allowGroupSubmission, assignmentUuid, accessToken])

  React.useEffect(() => {
    load()
  }, [load])

  if (!allowGroupSubmission) return null

  // A student is "in" whichever group came back with members populated —
  // the backend only reveals member identities for the caller's own group
  // (or to an instructor, who doesn't see this student-facing panel).
  const myGroup = groups?.find((g) => g.members !== null) ?? null

  const handleCreate = async () => {
    if (!assignmentUuid || !accessToken || !newGroupName.trim()) return
    setBusy(true)
    try {
      const res = await createAssignmentGroup(assignmentUuid, newGroupName.trim(), accessToken)
      if (res.success) {
        toast.success(t('activities.group_panel.created', { defaultValue: 'Team created.' }))
        setNewGroupName('')
        await load()
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  const handleJoin = async (groupUuid: string) => {
    if (!assignmentUuid || !accessToken) return
    setBusy(true)
    try {
      const res = await joinAssignmentGroup(assignmentUuid, groupUuid, accessToken)
      if (res.success) {
        toast.success(t('activities.group_panel.joined', { defaultValue: 'Joined the team.' }))
        await load()
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  const handleLeave = async () => {
    if (!assignmentUuid || !accessToken || !myGroup) return
    setBusy(true)
    try {
      const res = await leaveAssignmentGroup(assignmentUuid, myGroup.group_uuid, accessToken)
      if (res.success) {
        toast.success(t('activities.group_panel.left', { defaultValue: 'Left the team.' }))
        await load()
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  const handleSubmitForTeam = async () => {
    if (!assignmentUuid || !accessToken || !myGroup) return
    setBusy(true)
    try {
      const res = await submitAssignmentGroupForGrading(assignmentUuid, myGroup.group_uuid, accessToken)
      if (res.success) {
        const { submitted_user_ids, skipped_user_ids } = res.data || {}
        toast.success(
          res.data?.message ||
            t('activities.group_panel.submitted', { defaultValue: 'Submitted for the team.' })
        )
        if (skipped_user_ids?.length) {
          toast.error(
            t('activities.group_panel.some_skipped', {
              defaultValue: '{{count}} teammate(s) could not be submitted for — check with your instructor.',
              count: skipped_user_ids.length,
            })
          )
        }
        void submitted_user_ids
      } else {
        toast.error(res.data?.detail || t('common.something_went_wrong'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200/80 bg-white nice-shadow p-5 mb-5">
      <div className="flex items-center gap-2 mb-3">
        <Users size={16} className="text-indigo-500" />
        <p className="text-sm font-bold text-gray-900">
          {t('activities.group_panel.title', { defaultValue: 'Team submission' })}
        </p>
      </div>

      {(groupMinSize || groupMaxSize) && (
        <p className="text-[11px] text-gray-400 mb-3">
          {groupMinSize && groupMaxSize
            ? t('activities.group_panel.size_range', {
                defaultValue: 'Teams of {{min}}–{{max}}.',
                min: groupMinSize,
                max: groupMaxSize,
              })
            : groupMaxSize
              ? t('activities.group_panel.size_max', { defaultValue: 'Up to {{max}} per team.', max: groupMaxSize })
              : t('activities.group_panel.size_min', { defaultValue: 'At least {{min}} per team.', min: groupMinSize })}
        </p>
      )}

      {myGroup ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg bg-indigo-50 px-3 py-2">
            <div>
              <p className="text-xs font-bold text-indigo-900">{myGroup.name}</p>
              <p className="text-[11px] text-indigo-600">
                {t('activities.group_panel.member_count', {
                  defaultValue: '{{count}} member(s)',
                  count: myGroup.member_count,
                })}
              </p>
            </div>
            <ConfirmationModal
              confirmationButtonText={t('activities.group_panel.leave', { defaultValue: 'Leave team' })}
              confirmationMessage={t('activities.group_panel.leave_confirm', {
                defaultValue: 'You can join or create another team afterwards.',
              })}
              dialogTitle={t('activities.group_panel.leave', { defaultValue: 'Leave team' })}
              functionToExecute={handleLeave}
              status="warning"
              dialogTrigger={
                <button
                  type="button"
                  disabled={busy}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-indigo-700 bg-white rounded-lg nice-shadow hover:bg-indigo-100/60 transition-colors disabled:opacity-50"
                >
                  <LogOut size={11} />
                  {t('activities.group_panel.leave', { defaultValue: 'Leave team' })}
                </button>
              }
            />
          </div>
          <button
            type="button"
            onClick={handleSubmitForTeam}
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 h-9 px-4 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            <Send size={14} />
            {t('activities.group_panel.submit_for_team', { defaultValue: 'Submit for the whole team' })}
          </button>
          <p className="text-[10px] text-gray-400 leading-snug">
            {t('activities.group_panel.submit_hint', {
              defaultValue: 'This hands in your current answers for every teammate at once — make sure everyone is done first.',
            })}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups && groups.length > 0 && (
            <div className="space-y-1.5">
              {groups.map((g) => (
                <div
                  key={g.group_uuid}
                  className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-semibold text-gray-800">{g.name}</p>
                    <p className="text-[11px] text-gray-400">
                      {t('activities.group_panel.member_count', {
                        defaultValue: '{{count}} member(s)',
                        count: g.member_count,
                      })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleJoin(g.group_uuid)}
                    disabled={busy || g.is_full}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200/80 transition-colors disabled:opacity-50"
                  >
                    <Check size={11} />
                    {g.is_full
                      ? t('activities.group_panel.full', { defaultValue: 'Full' })
                      : t('activities.group_panel.join', { defaultValue: 'Join' })}
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder={t('activities.group_panel.new_team_placeholder', { defaultValue: 'New team name' })}
              className="flex-1 px-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors"
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={busy || !newGroupName.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              <Plus size={13} />
              {t('activities.group_panel.create', { defaultValue: 'Create' })}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
