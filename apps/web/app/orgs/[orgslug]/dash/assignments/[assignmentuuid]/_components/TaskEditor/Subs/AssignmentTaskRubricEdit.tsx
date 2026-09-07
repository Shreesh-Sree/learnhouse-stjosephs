'use client';
import { useAssignments } from '@components/Contexts/Assignments/AssignmentContext';
import { useAssignmentsTask, useAssignmentsTaskDispatch } from '@components/Contexts/Assignments/AssignmentsTaskContext';
import { useLHSession } from '@components/Contexts/LHSessionContext';
import { updateAssignmentTask } from '@services/courses/assignments';
import { Plus, Trash2, Info } from 'lucide-react';
import React from 'react';
import toast from 'react-hot-toast';
import { v4 as uuidv4 } from 'uuid';
import { useTranslation } from 'react-i18next';

interface Criterion {
    criterion_uuid: string;
    title: string;
    description?: string;
    max_points: number;
}

/**
 * An optional rubric layered on top of any task type — a list of scored
 * criteria the grading UI turns into a click-to-score widget (see
 * RubricGradingWidget.tsx). Stored in the task's own `contents.rubric`,
 * the same opaque-JSON pattern other per-task config (pool_size,
 * shuffle_questions, response_type) already uses, so this needs no
 * separate save action from the rest of the task's contents.
 *
 * A task with an empty rubric (or none) is graded exactly as before — this
 * is additive, not a replacement for the plain numeric grade input.
 */
export function AssignmentTaskRubricEdit() {
    const { t } = useTranslation();
    const session = useLHSession() as any;
    const access_token = session?.data?.tokens?.access_token;
    const assignmentTaskState = useAssignmentsTask() as any;
    const assignmentTaskStateHook = useAssignmentsTaskDispatch() as any;
    const assignment = useAssignments() as any;

    const contents = assignmentTaskState.assignmentTask.contents || {};
    const [criteria, setCriteria] = React.useState<Criterion[]>(
        Array.isArray(contents.rubric) ? contents.rubric : []
    );
    const [saving, setSaving] = React.useState(false);

    React.useEffect(() => {
        setCriteria(Array.isArray(contents.rubric) ? contents.rubric : []);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [assignmentTaskState.assignmentTask.assignment_task_uuid]);

    const totalPoints = criteria.reduce((acc, c) => acc + (Number(c.max_points) || 0), 0);

    const save = async (next: Criterion[]) => {
        setCriteria(next);
        setSaving(true);
        try {
            const res = await updateAssignmentTask(
                { contents: { ...contents, rubric: next } },
                assignmentTaskState.assignmentTask.assignment_task_uuid,
                assignment.assignment_object.assignment_uuid,
                access_token
            );
            if (res) {
                assignmentTaskStateHook({ type: 'reload' });
            } else {
                toast.error(t('dashboard.assignments.editor.task_editor.rubric.save_error', { defaultValue: 'Could not save the rubric.' }));
            }
        } finally {
            setSaving(false);
        }
    };

    const addCriterion = () => {
        save([...criteria, { criterion_uuid: uuidv4(), title: '', description: '', max_points: 10 }]);
    };

    const updateCriterion = (uuid: string, patch: Partial<Criterion>) => {
        setCriteria((prev) => prev.map((c) => (c.criterion_uuid === uuid ? { ...c, ...patch } : c)));
    };

    const removeCriterion = (uuid: string) => {
        save(criteria.filter((c) => c.criterion_uuid !== uuid));
    };

    return (
        <div className="space-y-4">
            <div className="flex items-start gap-2 text-xs text-gray-500 bg-gray-50 rounded-lg p-3">
                <Info size={14} className="mt-0.5 shrink-0" />
                <p>
                    {t('dashboard.assignments.editor.task_editor.rubric.info', {
                        defaultValue: 'Optional. When this task has criteria here, the grading screen shows a click-to-score rubric instead of (or alongside) a plain number — the final task score is scaled to 100 from the points awarded.',
                    })}
                </p>
            </div>

            {criteria.map((c) => (
                <div key={c.criterion_uuid} className="rounded-xl border border-gray-100 nice-shadow p-3 space-y-2">
                    <div className="flex items-center gap-2">
                        <input
                            type="text"
                            value={c.title}
                            onChange={(e) => updateCriterion(c.criterion_uuid, { title: e.target.value })}
                            onBlur={() => save(criteria)}
                            placeholder={t('dashboard.assignments.editor.task_editor.rubric.criterion_title_placeholder', { defaultValue: 'Criterion (e.g. Correctness)' })}
                            className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300"
                        />
                        <input
                            type="number"
                            min={0}
                            value={c.max_points}
                            onChange={(e) => updateCriterion(c.criterion_uuid, { max_points: Number(e.target.value) })}
                            onBlur={() => save(criteria)}
                            className="w-20 px-2 py-1.5 text-sm text-center rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300"
                        />
                        <button
                            type="button"
                            onClick={() => removeCriterion(c.criterion_uuid)}
                            className="p-1.5 text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                        >
                            <Trash2 size={14} />
                        </button>
                    </div>
                    <textarea
                        value={c.description || ''}
                        onChange={(e) => updateCriterion(c.criterion_uuid, { description: e.target.value })}
                        onBlur={() => save(criteria)}
                        placeholder={t('dashboard.assignments.editor.task_editor.rubric.criterion_description_placeholder', { defaultValue: 'What earns full points here? (optional)' })}
                        rows={2}
                        className="w-full px-3 py-1.5 text-xs rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 resize-none"
                    />
                </div>
            ))}

            <div className="flex items-center justify-between">
                <button
                    type="button"
                    onClick={addCriterion}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200/80 transition-colors disabled:opacity-50"
                >
                    <Plus size={13} />
                    {t('dashboard.assignments.editor.task_editor.rubric.add_criterion', { defaultValue: 'Add criterion' })}
                </button>
                {criteria.length > 0 && (
                    <p className="text-xs font-semibold text-gray-500">
                        {t('dashboard.assignments.editor.task_editor.rubric.total_points', {
                            defaultValue: '{{total}} points total',
                            total: totalPoints,
                        })}
                    </p>
                )}
            </div>
        </div>
    );
}
