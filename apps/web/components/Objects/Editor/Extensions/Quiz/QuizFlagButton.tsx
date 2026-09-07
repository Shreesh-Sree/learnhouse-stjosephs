import React from 'react'
import { Flag, X } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { createQuizFlag, QuizFlagReason } from '@services/courses/quizFlags'
import toast from 'react-hot-toast'

const REASONS: QuizFlagReason[] = ['incorrect_answer', 'unclear_wording', 'typo', 'other']

/**
 * Lets a student flag a problem with a quiz question they're taking — feeds
 * the instructor's review queue (course dashboard → "Flagged Questions").
 * Deliberately a tiny inline popover rather than a modal: this sits inside
 * an already-dense quiz block, and the interaction is a one-field pick plus
 * an optional note, not a form.
 */
export default function QuizFlagButton({
  activityUuid,
  quizId,
  questionId,
}: {
  activityUuid?: string
  quizId?: string
  questionId: string
}) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const [open, setOpen] = React.useState(false)
  const [reason, setReason] = React.useState<QuizFlagReason>('incorrect_answer')
  const [note, setNote] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [submitted, setSubmitted] = React.useState(false)

  if (!activityUuid || !quizId) return null

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await createQuizFlag(activityUuid, quizId, questionId, reason, note.trim() || null, access_token)
      setSubmitted(true)
      setOpen(false)
      toast.success(
        t('editor.blocks.quiz_block.flag_submitted', {
          defaultValue: 'Thanks — your instructor will take a look.',
        })
      )
    } catch (err: any) {
      toast.error(err?.message || t('common.something_went_wrong'))
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <span
        className="shrink-0 w-6 h-6 flex items-center justify-center text-emerald-500"
        title={t('editor.blocks.quiz_block.flag_submitted_title', { defaultValue: 'Flagged' })}
      >
        <Flag weight="fill" size={12} />
      </span>
    )
  }

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="w-6 h-6 flex items-center justify-center rounded-md text-neutral-400 hover:text-amber-600 hover:bg-amber-50 transition-colors outline-none"
        title={t('editor.blocks.quiz_block.flag_question', { defaultValue: 'Report a problem with this question' })}
      >
        <Flag weight="duotone" size={12} />
      </button>

      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-7 z-10 w-64 bg-white rounded-lg nice-shadow border border-neutral-100 p-3 space-y-2"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-neutral-700">
              {t('editor.blocks.quiz_block.flag_title', { defaultValue: 'What\'s wrong?' })}
            </p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-neutral-400 hover:text-neutral-700"
            >
              <X size={12} />
            </button>
          </div>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value as QuizFlagReason)}
            className="w-full text-xs border border-neutral-200 rounded-md px-2 py-1.5 outline-none"
          >
            {REASONS.map((r) => (
              <option key={r} value={r}>
                {t(`editor.blocks.quiz_block.flag_reason_${r}`, { defaultValue: r })}
              </option>
            ))}
          </select>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t('editor.blocks.quiz_block.flag_note_placeholder', {
              defaultValue: 'Anything else? (optional)',
            })}
            rows={2}
            className="w-full text-xs border border-neutral-200 rounded-md px-2 py-1.5 outline-none resize-none"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full text-xs font-medium py-1.5 rounded-md bg-neutral-900 text-white hover:bg-neutral-800 transition-colors disabled:opacity-50"
          >
            {submitting
              ? t('common.loading', { defaultValue: 'Loading…' })
              : t('editor.blocks.quiz_block.flag_submit', { defaultValue: 'Report' })}
          </button>
        </div>
      )}
    </div>
  )
}
