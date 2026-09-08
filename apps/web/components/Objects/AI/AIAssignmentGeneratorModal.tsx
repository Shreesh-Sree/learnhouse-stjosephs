'use client'
import React, { useState } from 'react'
import toast from 'react-hot-toast'
import { useQueryClient } from '@tanstack/react-query'
import {
  MagicWand,
  CircleNotch,
  Check,
  ListChecks,
  TextAa,
  Hash,
  FileText,
  Sparkle,
} from '@phosphor-icons/react'
import { useOrg } from '@components/Contexts/OrgContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'
import { generateAIAssignment } from '@services/ai/generation'
import { createActivity, deleteActivity } from '@services/courses/activities'
import { createAssignment, createAssignmentTask } from '@services/courses/assignments'
import { refreshCourseStructureCache } from '@services/courses/courses'
import { getErrorMessage } from '@services/utils/ts/errorMessage'

// AI-generated assessment: one prompt -> a full graded assignment (title,
// description, and N tasks with real, schema-valid questions — QUIZ options,
// FORM blanks, SHORT_ANSWER/NUMBER_ANSWER keys) previewed here, then created
// through the exact same activity -> assignment -> tasks sequence the manual
// "New Assignment" form uses, so what this produces is indistinguishable from
// something a teacher built by hand.

interface GeneratedTask {
  title: string
  description: string
  hint: string
  assignment_type: 'QUIZ' | 'FORM' | 'SHORT_ANSWER' | 'NUMBER_ANSWER' | 'FILE_SUBMISSION'
  contents: any
  max_grade_value: number
}
interface GeneratedPlan {
  title: string
  description: string
  grading_type: string
  tasks: GeneratedTask[]
}

const TASK_TYPES: { value: string; label: string; icon: React.ReactNode }[] = [
  { value: 'QUIZ', label: 'Quiz (multiple choice)', icon: <ListChecks size={14} weight="fill" /> },
  { value: 'FORM', label: 'Fill in the blank', icon: <TextAa size={14} weight="fill" /> },
  { value: 'SHORT_ANSWER', label: 'Short answer', icon: <FileText size={14} weight="fill" /> },
  { value: 'NUMBER_ANSWER', label: 'Numeric answer', icon: <Hash size={14} weight="fill" /> },
]

interface AIAssignmentGeneratorModalProps {
  course: any // { courseStructure, withUnpublishedActivities } — same shape the manual form takes
  chapterId: number
  onClose: () => void
  onCreated: () => void
}

const AIAssignmentGeneratorModal: React.FC<AIAssignmentGeneratorModalProps> = ({
  course,
  chapterId,
  onClose,
  onCreated,
}) => {
  const org = useOrg() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const queryClient = useQueryClient()
  const { track } = useLHAnalytics('learner')

  const [prompt, setPrompt] = useState('')
  const [numTasks, setNumTasks] = useState(3)
  const [allowedTypes, setAllowedTypes] = useState<string[]>(['QUIZ', 'SHORT_ANSWER'])
  const [generating, setGenerating] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [plan, setPlan] = useState<GeneratedPlan | null>(null)

  // The AI assignment-generation endpoint looks up Course.course_uuid directly
  // (not the bare form getCourseMetadata expects) — send it unstripped.
  const courseUuid = course?.courseStructure?.course_uuid

  const toggleType = (value: string) => {
    setAllowedTypes((prev) =>
      prev.includes(value) ? prev.filter((t) => t !== value) : [...prev, value]
    )
  }

  const handleGenerate = async () => {
    if (!prompt.trim() || generating || !org?.id || !courseUuid) return
    setGenerating(true)
    setError(null)
    setPlan(null)
    try {
      const res = await generateAIAssignment(
        {
          org_id: org.id,
          course_uuid: courseUuid,
          prompt: prompt.trim(),
          num_tasks: numTasks,
          allowed_task_types: allowedTypes.length ? allowedTypes : undefined,
        },
        access_token
      )
      if (!res.success) {
        setError(res.data?.detail || 'Assessment generation failed. Please try again.')
        return
      }
      setPlan(res.data.plan)
    } catch {
      setError('Assessment generation failed. Please try again.')
    } finally {
      setGenerating(false)
    }
  }

  const handleCreate = async () => {
    if (!plan || creating) return
    setCreating(true)

    let activity_res: any
    try {
      activity_res = await createActivity(
        {
          name: plan.title,
          chapter_id: chapterId,
          activity_type: 'TYPE_ASSIGNMENT',
          activity_sub_type: 'SUBTYPE_ASSIGNMENT_ANY',
          published: false,
          course_id: course?.courseStructure.id,
        },
        chapterId,
        org?.id,
        access_token
      )
    } catch (e) {
      console.error('Failed to create assignment activity:', e)
      toast.error('Failed to create assessment. Please try again.')
      setCreating(false)
      return
    }

    let assignmentRes: any
    try {
      assignmentRes = await createAssignment(
        {
          title: plan.title,
          description: plan.description,
          due_date: null,
          grading_type: plan.grading_type || 'PERCENTAGE',
          ungraded: false,
          auto_grading: true,
          anti_copy_paste: false,
          show_correct_answers: false,
          allow_retries: false,
          max_retries: 0,
          course_id: course?.courseStructure.id,
          org_id: org?.id,
          chapter_id: chapterId,
          activity_id: activity_res?.id,
        },
        access_token
      )
    } catch (e) {
      console.error('Failed to create assessment:', e)
      toast.error('Failed to create assessment. Please try again.')
      await deleteActivity(activity_res.activity_uuid, access_token).catch(() => {})
      setCreating(false)
      return
    }

    if (!assignmentRes.success) {
      toast.error(getErrorMessage(assignmentRes.data?.detail, 'Failed to create assessment.'))
      await deleteActivity(activity_res.activity_uuid, access_token).catch(() => {})
      setCreating(false)
      return
    }

    const assignmentUuid = assignmentRes.data?.assignment_uuid
    let tasksFailed = 0
    for (const task of plan.tasks) {
      try {
        const taskRes = await createAssignmentTask(
          {
            title: task.title,
            description: task.description,
            hint: task.hint || '',
            assignment_type: task.assignment_type,
            contents: task.contents,
            max_grade_value: task.max_grade_value ?? 100,
          },
          assignmentUuid,
          access_token
        )
        if (!taskRes?.success && taskRes?.success !== undefined) tasksFailed += 1
      } catch (e) {
        console.error('Failed to create assessment task:', e)
        tasksFailed += 1
      }
    }

    track(AnalyticsEvent.AssignmentCreated, {
      grading_type: plan.grading_type,
      source: 'ai_generated',
      task_count: plan.tasks.length,
    })

    if (tasksFailed > 0) {
      toast.error(
        `Assessment created, but ${tasksFailed} of ${plan.tasks.length} question${plan.tasks.length === 1 ? '' : 's'} failed to save. You can add them manually.`
      )
    } else {
      toast.success('Assessment created with ' + plan.tasks.length + ' question' + (plan.tasks.length === 1 ? '' : 's') + '.')
    }

    try {
      await refreshCourseStructureCache(queryClient, course.courseStructure.course_uuid, access_token)
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      queryClient.invalidateQueries({ queryKey: ['assignments'] })
    } catch (e) {
      console.error('Failed to refresh course structure cache after assessment creation:', e)
    }

    setCreating(false)
    onCreated()
  }

  return (
    <div className="flex flex-col h-full">
      {!plan ? (
        <div className="p-4 space-y-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="Describe the assessment — e.g. 'A 10-question quiz on binary search trees, medium difficulty'"
            className="w-full p-3 border border-neutral-200 rounded-xl resize-none focus:outline-hidden focus:ring-2 focus:ring-neutral-900/10 text-sm"
          />

          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-neutral-500">Questions</label>
            <input
              type="number"
              min={1}
              max={15}
              value={numTasks}
              onChange={(e) => setNumTasks(Math.max(1, Math.min(15, Number(e.target.value) || 1)))}
              className="w-16 px-2 py-1 border border-neutral-200 rounded-lg text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-neutral-500 block mb-1.5">Question types</label>
            <div className="flex flex-wrap gap-2">
              {TASK_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => toggleType(t.value)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    allowedTypes.includes(t.value)
                      ? 'bg-neutral-900 text-white border-neutral-900'
                      : 'bg-white text-neutral-500 border-neutral-200 hover:border-neutral-300'
                  }`}
                >
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGenerate}
            disabled={!prompt.trim() || generating}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-neutral-900 text-white text-sm font-semibold disabled:opacity-40 hover:bg-neutral-800 transition-colors"
          >
            {generating ? (
              <>
                <CircleNotch size={16} className="animate-spin" /> Generating…
              </>
            ) : (
              <>
                <MagicWand size={16} weight="fill" /> Generate Assessment
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-neutral-100">
            <h3 className="font-bold text-base">{plan.title}</h3>
            <p className="text-sm text-neutral-500 mt-1">{plan.description}</p>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {plan.tasks.map((task, i) => (
              <TaskPreview key={i} task={task} index={i} />
            ))}
          </div>

          <div className="p-4 border-t border-neutral-100 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPlan(null)}
              disabled={creating}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-neutral-600 hover:bg-neutral-100 transition-colors disabled:opacity-40"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-neutral-900 text-white text-sm font-semibold disabled:opacity-40 hover:bg-neutral-800 transition-colors"
            >
              {creating ? (
                <>
                  <CircleNotch size={16} className="animate-spin" /> Creating…
                </>
              ) : (
                <>
                  <Check size={16} weight="bold" /> Create Assessment
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function TaskPreview({ task, index }: { task: GeneratedTask; index: number }) {
  const typeInfo = TASK_TYPES.find((t) => t.value === task.assignment_type)
  return (
    <div className="border border-neutral-200 rounded-xl p-3.5">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-neutral-400 bg-neutral-100 px-1.5 py-0.5 rounded">
          {typeInfo?.icon}
          {typeInfo?.label || task.assignment_type}
        </span>
        <span className="text-[11px] text-neutral-400">Q{index + 1}</span>
      </div>
      <p className="text-sm font-semibold text-neutral-800">{task.title}</p>
      {task.description && (
        <p className="text-xs text-neutral-500 mt-0.5">{task.description}</p>
      )}

      {task.assignment_type === 'QUIZ' && Array.isArray(task.contents?.questions) && (
        <div className="mt-2.5 space-y-2.5">
          {task.contents.questions.map((q: any, qi: number) => (
            <div key={qi} className="text-xs">
              <p className="font-medium text-neutral-700 mb-1">{q.questionText}</p>
              <div className="space-y-1">
                {(q.options || []).map((opt: any, oi: number) => (
                  <div
                    key={oi}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-md ${
                      opt.assigned_right_answer
                        ? 'bg-green-50 text-green-700'
                        : 'text-neutral-500'
                    }`}
                  >
                    {opt.assigned_right_answer ? (
                      <Check size={12} weight="bold" />
                    ) : (
                      <span className="w-3 inline-block" />
                    )}
                    {opt.text}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {task.assignment_type === 'SHORT_ANSWER' && (
        <div className="mt-2 text-xs text-neutral-500">
          <span className="font-medium text-neutral-700">Accepted: </span>
          {(task.contents?.correct_answers || []).join(', ')}
        </div>
      )}

      {task.assignment_type === 'NUMBER_ANSWER' && (
        <div className="mt-2 text-xs text-neutral-500">
          <span className="font-medium text-neutral-700">Answer: </span>
          {task.contents?.correct_value}
          {task.contents?.unit ? ` ${task.contents.unit}` : ''}
          {task.contents?.tolerance ? ` (± ${task.contents.tolerance})` : ''}
        </div>
      )}

      {task.assignment_type === 'FORM' && Array.isArray(task.contents?.questions) && (
        <div className="mt-2.5 space-y-2 text-xs">
          {task.contents.questions.map((q: any, qi: number) => (
            <div key={qi}>
              <p className="text-neutral-700 mb-1">{q.questionText}</p>
              <div className="flex flex-wrap gap-1.5">
                {(q.blanks || []).map((b: any, bi: number) => (
                  <span key={bi} className="bg-neutral-100 text-neutral-600 px-2 py-0.5 rounded">
                    {b.correctAnswer}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {task.assignment_type === 'FILE_SUBMISSION' && (
        <div className="mt-2 text-xs text-neutral-400 flex items-center gap-1">
          <Sparkle size={12} /> Learner uploads a file — manually graded
        </div>
      )}
    </div>
  )
}

export default AIAssignmentGeneratorModal
