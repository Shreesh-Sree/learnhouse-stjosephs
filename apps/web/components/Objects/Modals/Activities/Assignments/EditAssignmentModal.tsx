import React from 'react';
import {
    deleteAssignmentSolutionFile,
    downloadAssignmentSebConfig,
    updateAssignment,
    updateAssignmentSolutionFile,
} from '@services/courses/assignments';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query/keys';
import toast from 'react-hot-toast';
import * as Form from '@radix-ui/react-form';
import { useFormik } from 'formik';
import Modal from '@components/Objects/StyledElements/Modal/Modal';
import { useTranslation } from 'react-i18next';

// Same input class used by the create-assignment modal, so both forms look
// identical to the user.
const inputClass =
    'w-full h-9 px-3 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors';
const textareaClass =
    'w-full px-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 outline-none focus:border-gray-300 focus:ring-1 focus:ring-gray-200 transition-colors resize-none';
const labelClass = 'text-sm font-medium text-gray-700';
const errorClass = 'text-xs text-red-500';
import {
    ALargeSmall,
    Hash,
    Percent,
    ThumbsUp,
    GraduationCap,
    Check,
    Zap,
    Shield,
    AlertTriangle,
    Eye,
    RotateCcw,
    Target,
    Infinity as InfinityIcon,
    ClipboardCheck,
    BookOpenCheck,
    Lock,
    Paperclip,
    Trash2,
    Upload,
    ShieldCheck,
    KeyRound,
    Timer,
    Download,
    Camera,
    Wifi,
    Users,
} from 'lucide-react';

type GradingType = 'ALPHABET' | 'NUMERIC' | 'PERCENTAGE' | 'PASS_FAIL' | 'GPA_SCALE';
type SolutionReveal = 'NEVER' | 'ON_SUBMISSION' | 'AFTER_GRADING';

interface Assignment {
    assignment_uuid: string;
    title: string;
    description: string;
    due_date?: string;
    grading_type?: GradingType;
    auto_grading?: boolean;
    anti_copy_paste?: boolean;
    show_correct_answers?: boolean;
    allow_retries?: boolean;
    max_retries?: number;
    pass_threshold_percentage?: number | null;
    ungraded?: boolean;
    solution?: string | null;
    solution_file?: string | null;
    solution_reveal?: SolutionReveal;
    require_safe_exam_browser?: boolean;
    seb_quit_password?: string | null;
    time_limit_minutes?: number | null;
    require_webcam_proctoring?: boolean;
    require_ip_allowlist?: boolean;
    ip_allowlist?: string | null;
    allow_group_submission?: boolean;
    group_min_size?: number | null;
    group_max_size?: number | null;
    assignment_tasks?: any[];
}

interface EditAssignmentFormProps {
    onClose: () => void;
    assignment: Assignment;
    accessToken: string;
}

interface EditAssignmentModalProps {
    isOpen: boolean;
    onClose: () => void;
    assignment: Assignment;
    accessToken: string;
}

const GRADING_TYPES: {
    value: GradingType;
    labelKey: string;
    descriptionKey: string;
    icon: React.ReactNode;
    color: string;
    selectedBorder: string;
    selectedBg: string;
    illustration: string;
}[] = [
    {
        value: 'ALPHABET',
        labelKey: 'dashboard.assignments.modals.edit.form.grading_types.alphabet',
        descriptionKey: 'dashboard.assignments.modals.edit.form.grading_type_descriptions.alphabet',
        icon: <ALargeSmall size={20} />,
        color: 'text-violet-600',
        selectedBorder: 'border-violet-400',
        selectedBg: 'bg-violet-50',
        illustration: 'A  B  C',
    },
    {
        value: 'NUMERIC',
        labelKey: 'dashboard.assignments.modals.edit.form.grading_types.numeric',
        descriptionKey: 'dashboard.assignments.modals.edit.form.grading_type_descriptions.numeric',
        icon: <Hash size={20} />,
        color: 'text-blue-600',
        selectedBorder: 'border-blue-400',
        selectedBg: 'bg-blue-50',
        illustration: '0 — 100',
    },
    {
        value: 'PERCENTAGE',
        labelKey: 'dashboard.assignments.modals.edit.form.grading_types.percentage',
        descriptionKey: 'dashboard.assignments.modals.edit.form.grading_type_descriptions.percentage',
        icon: <Percent size={20} />,
        color: 'text-emerald-600',
        selectedBorder: 'border-emerald-400',
        selectedBg: 'bg-emerald-50',
        illustration: '85%',
    },
    {
        value: 'PASS_FAIL',
        labelKey: 'dashboard.assignments.modals.edit.form.grading_types.pass_fail',
        descriptionKey: 'dashboard.assignments.modals.edit.form.grading_type_descriptions.pass_fail',
        icon: <ThumbsUp size={20} />,
        color: 'text-amber-600',
        selectedBorder: 'border-amber-400',
        selectedBg: 'bg-amber-50',
        illustration: 'P / F',
    },
    {
        value: 'GPA_SCALE',
        labelKey: 'dashboard.assignments.modals.edit.form.grading_types.gpa_scale',
        descriptionKey: 'dashboard.assignments.modals.edit.form.grading_type_descriptions.gpa_scale',
        icon: <GraduationCap size={20} />,
        color: 'text-rose-600',
        selectedBorder: 'border-rose-400',
        selectedBg: 'bg-rose-50',
        illustration: '0.0 — 4.0',
    },
];

// The date input speaks YYYY-MM-DD and nothing else. Values it cannot show
// come back as '' rather than being carried invisibly through the form.
function toDateInputValue(raw?: string | null): string {
    const match = /^\d{4}-\d{2}-\d{2}/.exec((raw ?? '').trim());
    return match ? match[0] : '';
}

const EditAssignmentForm: React.FC<EditAssignmentFormProps> = ({
    onClose,
    assignment,
    accessToken
}) => {
    const { t } = useTranslation()
    const queryClient = useQueryClient()

    // Auto-grading is incompatible with file-submission tasks — those need
    // human review. If any such task exists, we force the toggle off and
    // show a note explaining why.
    const hasFileSubmissionTask = (assignment.assignment_tasks || []).some(
        (t: any) => t.assignment_type === 'FILE_SUBMISSION'
    );

    // The corrigé document is staged locally and only sent on save, so a
    // teacher who cancels the modal doesn't leave a half-applied change behind.
    const [solutionFile, setSolutionFile] = React.useState<File | null>(null);
    const [removeSolutionFile, setRemoveSolutionFile] = React.useState(false);
    const [isDownloadingSeb, setIsDownloadingSeb] = React.useState(false);

    const handleDownloadSebConfig = async () => {
        setIsDownloadingSeb(true);
        try {
            const file = await downloadAssignmentSebConfig(assignment.assignment_uuid, accessToken);
            const url = URL.createObjectURL(file);
            const a = document.createElement('a');
            a.href = url;
            a.download = file.name;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (_error) {
            toast.error(
                t('dashboard.assignments.modals.edit.form.seb_download_error', {
                    defaultValue: "Couldn't download the SEB config file.",
                })
            );
        } finally {
            setIsDownloadingSeb(false);
        }
    };

    const formik = useFormik({
        initialValues: {
            title: assignment.title || '',
            description: assignment.description || '',
            // `<input type="date">` shows nothing for a value carrying a time
            // component, so a stored "2026-01-01T09:00:00" would render as an
            // empty field the teacher reads as "no deadline" — and, now that
            // the field is optional and no longer blocks submit, quietly save
            // the old deadline straight back. Trim it to the day the input can
            // actually display.
            due_date: toDateInputValue(assignment.due_date),
            grading_type: assignment.grading_type || 'ALPHABET',
            auto_grading: assignment.auto_grading || false,
            anti_copy_paste: assignment.anti_copy_paste || false,
            show_correct_answers: assignment.show_correct_answers || false,
            allow_retries: assignment.allow_retries || false,
            // 0 means unlimited — kept as a number so the input below stays
            // numeric and the backend doesn't have to coerce strings.
            max_retries:
                typeof assignment.max_retries === 'number' ? assignment.max_retries : 0,
            // Empty string = "use the grading-type default"; a number overrides
            // the passing line for this assignment.
            pass_threshold_percentage:
                typeof assignment.pass_threshold_percentage === 'number'
                    ? assignment.pass_threshold_percentage
                    : '',
            // Formative mode: the assignment is handed in but never marked.
            ungraded: assignment.ungraded || false,
            solution: assignment.solution || '',
            solution_reveal: (assignment.solution_reveal || 'NEVER') as SolutionReveal,
            require_safe_exam_browser: assignment.require_safe_exam_browser || false,
            // The break-glass quit password (see Phase 2/3 of the SEB
            // integration): irrelevant to the normal submit-then-auto-exit
            // flow, only used if a proctor has to force-quit a stuck session.
            seb_quit_password: assignment.seb_quit_password || '',
            time_limit_enabled: typeof assignment.time_limit_minutes === 'number',
            time_limit_minutes:
                typeof assignment.time_limit_minutes === 'number' ? assignment.time_limit_minutes : 60,
            require_webcam_proctoring: assignment.require_webcam_proctoring || false,
            require_ip_allowlist: assignment.require_ip_allowlist || false,
            ip_allowlist: assignment.ip_allowlist || '',
            allow_group_submission: assignment.allow_group_submission || false,
            group_min_size: typeof assignment.group_min_size === 'number' ? assignment.group_min_size : '',
            group_max_size: typeof assignment.group_max_size === 'number' ? assignment.group_max_size : '',
        },
        enableReinitialize: true,
        onSubmit: async (values, { setSubmitting }) => {
            // Never send auto_grading=true when the assignment has a file task.
            // Also drop max_retries back to 0 when retries are turned off so a
            // stale number doesn't sit in the DB and reappear if the teacher
            // toggles retries back on later.
            const payload: any = hasFileSubmissionTask
                ? { ...values, auto_grading: false }
                : { ...values };
            if (!payload.allow_retries) {
                payload.max_retries = 0;
            }
            // Clearing the date means "no deadline". Send null, not the empty
            // string the input clears itself to, so the column reads as unset.
            payload.due_date = values.due_date || null;
            // Same convention for the quit password: an emptied field clears
            // it in the DB rather than storing an empty string.
            payload.seb_quit_password = values.seb_quit_password || null;
            payload.ip_allowlist = values.ip_allowlist || null;
            // Blank -> null (no bound in that direction), same convention as
            // pass_threshold_percentage above.
            payload.group_min_size =
                values.group_min_size === '' || values.group_min_size === null
                    ? null
                    : Math.max(1, Number(values.group_min_size));
            payload.group_max_size =
                values.group_max_size === '' || values.group_max_size === null
                    ? null
                    : Math.max(1, Number(values.group_max_size));
            // time_limit_enabled is a form-only toggle, never sent — it just
            // decides whether time_limit_minutes goes out as a number or an
            // explicit null (clearing it, same convention as due_date above).
            payload.time_limit_minutes = values.time_limit_enabled ? values.time_limit_minutes : null;
            delete payload.time_limit_enabled;
            // Formative mode owns the grading switches: an ungraded assignment
            // never auto-grades and has no answer key to reveal, so send the
            // consistent state rather than leaving stale flags in the DB that
            // would resurface if the teacher turns grading back on.
            if (payload.ungraded) {
                payload.auto_grading = false;
                payload.show_correct_answers = false;
                // AFTER_GRADING can never fire on something that is never
                // graded — fall back to unlocking on hand-in.
                if (payload.solution_reveal === 'AFTER_GRADING') {
                    payload.solution_reveal = 'ON_SUBMISSION';
                }
            }
            // Blank -> null (fall back to the default); otherwise clamp to 0-100.
            payload.pass_threshold_percentage =
                values.pass_threshold_percentage === '' ||
                values.pass_threshold_percentage === null
                    ? null
                    : Math.max(0, Math.min(100, Number(values.pass_threshold_percentage)));
            const toast_loading = toast.loading(t('dashboard.assignments.modals.edit.toasts.updating'));
            try {
                const res = await updateAssignment(payload, assignment.assignment_uuid, accessToken);
                if (res.success) {
                    // The corrigé document lives behind its own endpoint (it is a
                    // file upload), so it is applied after the field update and
                    // only when the teacher actually staged a change.
                    if (removeSolutionFile) {
                        await deleteAssignmentSolutionFile(assignment.assignment_uuid, accessToken);
                    } else if (solutionFile) {
                        const fileRes = await updateAssignmentSolutionFile(
                            solutionFile,
                            assignment.assignment_uuid,
                            accessToken
                        );
                        if (!fileRes.success) {
                            toast.error(
                                t('dashboard.assignments.modals.edit.toasts.solution_file_error', {
                                    defaultValue: "The model answer document couldn't be uploaded.",
                                })
                            );
                        }
                    }
                    queryClient.invalidateQueries({ queryKey: queryKeys.assignments.detail(assignment.assignment_uuid) });
                    toast.success(t('dashboard.assignments.modals.edit.toasts.success'));
                    onClose();
                } else {
                    toast.error(t('dashboard.assignments.modals.edit.toasts.error'));
                }
            } catch (_error) {
                toast.error(t('dashboard.assignments.modals.edit.toasts.error_detail'));
            } finally {
                toast.dismiss(toast_loading);
                setSubmitting(false);
            }
        }
    });

    return (
        <Form.Root onSubmit={formik.handleSubmit} className="space-y-5">
            {/* Basic info */}
            <Form.Field name="title" className="space-y-1.5">
                <Form.Label className={labelClass}>
                    {t('dashboard.assignments.modals.edit.form.title_label')}
                </Form.Label>
                <Form.Message match="valueMissing" className={errorClass}>
                    {t('dashboard.assignments.modals.edit.form.title_required')}
                </Form.Message>
                <Form.Control asChild>
                    <input
                        onChange={formik.handleChange}
                        value={formik.values.title}
                        type="text"
                        required
                        className={inputClass}
                    />
                </Form.Control>
            </Form.Field>

            <Form.Field name="description" className="space-y-1.5">
                <Form.Label className={labelClass}>
                    {t('dashboard.assignments.modals.edit.form.description_label')}
                </Form.Label>
                <Form.Message match="valueMissing" className={errorClass}>
                    {t('dashboard.assignments.modals.edit.form.description_required')}
                </Form.Message>
                <Form.Control asChild>
                    <textarea
                        onChange={formik.handleChange}
                        value={formik.values.description}
                        required
                        rows={3}
                        className={textareaClass}
                    />
                </Form.Control>
            </Form.Field>

            {/* Optional: a self-paced course has no date that means anything to
                a learner who enrolled today. */}
            <Form.Field name="due_date" className="space-y-1.5">
                <div className="flex items-center justify-between">
                    <Form.Label className={labelClass}>
                        {t('dashboard.assignments.modals.edit.form.due_date_label')}
                    </Form.Label>
                    {formik.values.due_date && (
                        <button
                            type="button"
                            onClick={() => formik.setFieldValue('due_date', '', false)}
                            className="text-[10px] font-medium text-gray-400 hover:text-gray-700 transition-colors"
                        >
                            {t('dashboard.assignments.modals.edit.form.due_date_clear')}
                        </button>
                    )}
                </div>
                <Form.Control asChild>
                    <input
                        type="date"
                        onChange={formik.handleChange}
                        value={formik.values.due_date}
                        className={inputClass}
                    />
                </Form.Control>
                <p className="text-[10px] text-gray-400">
                    {t('dashboard.assignments.modals.edit.form.due_date_hint')}
                </p>
            </Form.Field>

            {/* Formative mode. Deliberately above the grading settings: turning
                it on removes most of them, so the teacher sees the cause before
                the effect. */}
            <UngradedRow
                checked={formik.values.ungraded}
                onChange={(v) => formik.setFieldValue('ungraded', v, true)}
                label={t('dashboard.assignments.modals.edit.form.ungraded_label', { defaultValue: 'Formative — no grading' })}
                description={t('dashboard.assignments.modals.edit.form.ungraded_description', { defaultValue: 'Learners hand their work in and it is never marked. No score, no pass or fail — pair it with a model answer below for self-assessment.' })}
            />

            {/* Grading type */}
            {!formik.values.ungraded && (
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <p className={labelClass}>
                        {t('dashboard.assignments.modals.edit.form.grading_type_label')}
                    </p>
                    <p className="text-[10px] text-gray-400">
                        {t('dashboard.assignments.modals.edit.form.grading_type_hint')}
                    </p>
                </div>
                <div className="grid grid-cols-3 gap-2.5">
                    {GRADING_TYPES.map((gt) => {
                        const isSelected = formik.values.grading_type === gt.value;
                        return (
                            <button
                                key={gt.value}
                                type="button"
                                onClick={() => formik.setFieldValue('grading_type', gt.value, true)}
                                className={`relative flex flex-col items-center text-center p-4 rounded-xl nice-shadow bg-white transition-all cursor-pointer ${
                                    isSelected
                                        ? `${gt.selectedBg} ring-2 ${gt.selectedBorder.replace('border-', 'ring-')}`
                                        : 'hover:bg-gray-50/60'
                                }`}
                            >
                                {isSelected && (
                                    <div className={`absolute top-2 end-2 w-4 h-4 rounded-full flex items-center justify-center ${gt.color} bg-white nice-shadow`}>
                                        <Check size={10} strokeWidth={3} />
                                    </div>
                                )}
                                <div className={`text-lg font-mono font-bold mb-2 tracking-wider ${isSelected ? gt.color : 'text-gray-300'}`}>
                                    {gt.illustration}
                                </div>
                                <div className={`mb-1 ${isSelected ? gt.color : 'text-gray-400'}`}>
                                    {gt.icon}
                                </div>
                                <p className={`text-xs font-bold ${isSelected ? 'text-gray-900' : 'text-gray-500'}`}>
                                    {t(gt.labelKey)}
                                </p>
                                <p className='text-[10px] text-gray-400 mt-0.5 leading-tight'>
                                    {t(gt.descriptionKey)}
                                </p>
                            </button>
                        );
                    })}
                </div>
            </div>
            )}

            {/* Grading options */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <p className={labelClass}>
                        {t('dashboard.assignments.modals.edit.form.grading_options_label')}
                    </p>
                    <p className="text-[10px] text-gray-400">
                        {t('dashboard.assignments.modals.edit.form.grading_options_hint')}
                    </p>
                </div>
                <div className="space-y-2">
                    {!formik.values.ungraded && (
                    <ToggleRow
                        icon={<Zap size={16} className="text-amber-500" />}
                        label={t('dashboard.assignments.modals.edit.form.auto_grading_label')}
                        description={
                            hasFileSubmissionTask
                                ? t('dashboard.assignments.modals.edit.form.auto_grading_disabled_file')
                                : t('dashboard.assignments.modals.edit.form.auto_grading_description')
                        }
                        checked={!hasFileSubmissionTask && formik.values.auto_grading}
                        disabled={hasFileSubmissionTask}
                        onChange={(v) => formik.setFieldValue('auto_grading', v, true)}
                        warning={hasFileSubmissionTask}
                    />
                    )}
                    <ToggleRow
                        icon={<Shield size={16} className="text-cyan-500" />}
                        label={t('dashboard.assignments.modals.edit.form.anti_copy_paste_label')}
                        description={t('dashboard.assignments.modals.edit.form.anti_copy_paste_description')}
                        checked={formik.values.anti_copy_paste}
                        onChange={(v) => formik.setFieldValue('anti_copy_paste', v, true)}
                    />
                    {!formik.values.ungraded && (
                    <ToggleRow
                        icon={<Eye size={16} className="text-indigo-500" />}
                        label={t('dashboard.assignments.modals.edit.form.show_correct_answers_label')}
                        description={t('dashboard.assignments.modals.edit.form.show_correct_answers_description')}
                        checked={formik.values.show_correct_answers}
                        onChange={(v) => formik.setFieldValue('show_correct_answers', v, true)}
                    />
                    )}
                    <RetryRow
                        allowRetries={formik.values.allow_retries}
                        maxRetries={formik.values.max_retries}
                        onAllowChange={(v) => formik.setFieldValue('allow_retries', v, true)}
                        onMaxChange={(n) => formik.setFieldValue('max_retries', n, true)}
                        labelAllow={t('dashboard.assignments.modals.edit.form.allow_retries_label')}
                        descriptionAllow={
                            // The default copy says retries happen "after it's
                            // graded", which never comes true in formative mode.
                            formik.values.ungraded
                                ? t('dashboard.assignments.modals.edit.form.allow_retries_description_ungraded', {
                                      defaultValue:
                                          'Let learners reset and hand the assignment in again. Each retry wipes their previous work and re-locks the model answer.',
                                  })
                                : t('dashboard.assignments.modals.edit.form.allow_retries_description')
                        }
                        labelMax={t('dashboard.assignments.modals.edit.form.max_retries_label')}
                        helperUnlimited={t('dashboard.assignments.modals.edit.form.max_retries_unlimited')}
                        helperBounded={t('dashboard.assignments.modals.edit.form.max_retries_bounded')}
                    />
                    {!formik.values.ungraded && (
                    <PassThresholdRow
                        value={formik.values.pass_threshold_percentage}
                        onChange={(v) => formik.setFieldValue('pass_threshold_percentage', v, true)}
                        label={t('dashboard.assignments.modals.edit.form.pass_threshold_label', { defaultValue: 'Passing threshold' })}
                        description={t('dashboard.assignments.modals.edit.form.pass_threshold_description', { defaultValue: 'Minimum score to pass. Leave blank to use the default (50%, or 60% for letter grades).' })}
                        placeholder={t('dashboard.assignments.modals.edit.form.pass_threshold_placeholder', { defaultValue: 'Auto' })}
                    />
                    )}
                </div>
            </div>

            {/* Exam security */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <p className={labelClass}>
                        {t('dashboard.assignments.modals.edit.form.exam_security_label', { defaultValue: 'Exam security' })}
                    </p>
                </div>
                <SEBRow
                    checked={formik.values.require_safe_exam_browser}
                    onChange={(v) => formik.setFieldValue('require_safe_exam_browser', v, true)}
                    quitPassword={formik.values.seb_quit_password}
                    onQuitPasswordChange={(v) => formik.setFieldValue('seb_quit_password', v, true)}
                    savedEnabled={!!assignment.require_safe_exam_browser}
                    onDownload={handleDownloadSebConfig}
                    isDownloading={isDownloadingSeb}
                />
                <TimeLimitRow
                    enabled={formik.values.time_limit_enabled}
                    onEnabledChange={(v) => formik.setFieldValue('time_limit_enabled', v, true)}
                    minutes={formik.values.time_limit_minutes}
                    onMinutesChange={(v) => formik.setFieldValue('time_limit_minutes', v, true)}
                />
                <ToggleRow
                    icon={<Camera size={16} className="text-rose-500" />}
                    label={t('dashboard.assignments.modals.edit.form.webcam_proctoring_label', { defaultValue: 'Webcam proctoring' })}
                    description={t('dashboard.assignments.modals.edit.form.webcam_proctoring_description', {
                        defaultValue: 'Periodically captures a photo from the learner\'s webcam during the attempt, visible only to you. Learners see an explicit consent screen and can decline without being blocked.',
                    })}
                    checked={formik.values.require_webcam_proctoring}
                    onChange={(v) => formik.setFieldValue('require_webcam_proctoring', v, true)}
                />
                <IpAllowlistRow
                    checked={formik.values.require_ip_allowlist}
                    onChange={(v) => formik.setFieldValue('require_ip_allowlist', v, true)}
                    allowlist={formik.values.ip_allowlist}
                    onAllowlistChange={(v) => formik.setFieldValue('ip_allowlist', v, true)}
                />
            </div>

            {/* Group submission */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <p className={labelClass}>
                        {t('dashboard.assignments.modals.edit.form.group_submission_section_label', { defaultValue: 'Team submission' })}
                    </p>
                </div>
                <GroupSubmissionRow
                    checked={formik.values.allow_group_submission}
                    onChange={(v) => formik.setFieldValue('allow_group_submission', v, true)}
                    minSize={formik.values.group_min_size}
                    onMinSizeChange={(v) => formik.setFieldValue('group_min_size', v, true)}
                    maxSize={formik.values.group_max_size}
                    onMaxSizeChange={(v) => formik.setFieldValue('group_max_size', v, true)}
                />
            </div>

            {/* Model answer ("corrigé") */}
            <SolutionSection
                ungraded={formik.values.ungraded}
                solution={formik.values.solution}
                onSolutionChange={(v) => formik.setFieldValue('solution', v, true)}
                reveal={formik.values.solution_reveal}
                onRevealChange={(v) => formik.setFieldValue('solution_reveal', v, true)}
                currentFileName={removeSolutionFile ? null : assignment.solution_file ?? null}
                stagedFile={solutionFile}
                onStageFile={(f) => {
                    setSolutionFile(f);
                    setRemoveSolutionFile(false);
                }}
                onRemoveFile={() => {
                    setSolutionFile(null);
                    setRemoveSolutionFile(true);
                }}
            />

            <div className="flex justify-end space-x-3">
                <button
                    type="button"
                    onClick={onClose}
                    className="inline-flex items-center justify-center h-9 px-5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                >
                    {t('dashboard.assignments.modals.edit.form.cancel')}
                </button>
                <Form.Submit asChild>
                    <button
                        type="submit"
                        disabled={formik.isSubmitting}
                        className="inline-flex items-center justify-center h-9 px-5 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
                    >
                        {formik.isSubmitting ? t('dashboard.assignments.modals.edit.form.saving') : t('dashboard.assignments.modals.edit.form.save')}
                    </button>
                </Form.Submit>
            </div>
        </Form.Root>
    );
};

const EditAssignmentModal: React.FC<EditAssignmentModalProps> = ({
    isOpen,
    onClose,
    assignment,
    accessToken
}) => {
    const { t } = useTranslation()
    return (
        <Modal
            isDialogOpen={isOpen}
            onOpenChange={onClose}
            minHeight="md"
            minWidth="lg"
            dialogContent={
                <EditAssignmentForm
                    onClose={onClose}
                    assignment={assignment}
                    accessToken={accessToken}
                />
            }
            dialogTitle={t('dashboard.assignments.modals.edit.title')}
            dialogDescription={t('dashboard.assignments.modals.edit.description')}
            dialogTrigger={null}
        />
    );
};

// Formative mode gets its own card rather than a row in the grading options
// list: switching it on removes most of that list, so it needs to read as the
// decision it is, not as one more checkbox inside what it disables.
function UngradedRow({
    checked,
    onChange,
    label,
    description,
}: {
    checked: boolean;
    onChange: (_next: boolean) => void;
    label: string;
    description: string;
}) {
    return (
        <div className={`flex items-start justify-between gap-3 p-3.5 rounded-xl border nice-shadow transition-colors ${
            checked ? 'bg-teal-50/70 border-teal-200' : 'bg-white border-gray-100'
        }`}>
            <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <div className="mt-0.5 flex-none">
                    <ClipboardCheck size={17} className={checked ? 'text-teal-600' : 'text-gray-400'} />
                </div>
                <div className="flex flex-col min-w-0">
                    <p className="text-xs font-bold text-gray-900">{label}</p>
                    <p className="text-[10px] text-gray-500 leading-snug mt-0.5">{description}</p>
                </div>
            </div>
            <button
                type="button"
                onClick={() => onChange(!checked)}
                aria-pressed={checked}
                aria-label={label}
                className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    checked ? 'bg-teal-600' : 'bg-gray-200 hover:bg-gray-300'
                }`}
            >
                <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                        checked ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                    }`}
                />
            </button>
        </div>
    );
}

// The model answer ("corrigé"): free text plus an optional document, and the
// rule that decides when a learner may read either. The API enforces that rule
// server-side — this form only chooses it.
function SolutionSection({
    ungraded,
    solution,
    onSolutionChange,
    reveal,
    onRevealChange,
    currentFileName,
    stagedFile,
    onStageFile,
    onRemoveFile,
}: {
    ungraded: boolean;
    solution: string;
    onSolutionChange: (_v: string) => void;
    reveal: SolutionReveal;
    onRevealChange: (_v: SolutionReveal) => void;
    currentFileName: string | null;
    stagedFile: File | null;
    onStageFile: (_f: File) => void;
    onRemoveFile: () => void;
}) {
    const { t } = useTranslation();
    const fileInputRef = React.useRef<HTMLInputElement | null>(null);

    // AFTER_GRADING can never fire on an assignment that is never graded, so it
    // is dropped from the choices in formative mode instead of offering a
    // setting that would silently never unlock.
    const revealOptions: { value: SolutionReveal; label: string; hint: string; icon: React.ReactNode }[] = [
        {
            value: 'NEVER',
            label: t('dashboard.assignments.modals.edit.form.solution_reveal_never', { defaultValue: 'Never' }),
            hint: t('dashboard.assignments.modals.edit.form.solution_reveal_never_hint', { defaultValue: 'Kept for you only' }),
            icon: <Lock size={14} />,
        },
        {
            value: 'ON_SUBMISSION',
            label: t('dashboard.assignments.modals.edit.form.solution_reveal_on_submission', { defaultValue: 'On hand-in' }),
            hint: t('dashboard.assignments.modals.edit.form.solution_reveal_on_submission_hint', { defaultValue: 'Unlocks the moment they submit' }),
            icon: <BookOpenCheck size={14} />,
        },
        ...(ungraded
            ? []
            : [
                  {
                      value: 'AFTER_GRADING' as SolutionReveal,
                      label: t('dashboard.assignments.modals.edit.form.solution_reveal_after_grading', { defaultValue: 'After grading' }),
                      hint: t('dashboard.assignments.modals.edit.form.solution_reveal_after_grading_hint', { defaultValue: 'Unlocks once marked' }),
                      icon: <Check size={14} />,
                  },
              ]),
    ];
    const effectiveReveal: SolutionReveal =
        ungraded && reveal === 'AFTER_GRADING' ? 'ON_SUBMISSION' : reveal;

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <p className={labelClass}>
                    {t('dashboard.assignments.modals.edit.form.solution_label', { defaultValue: 'Model answer' })}
                </p>
                <p className="text-[10px] text-gray-400">
                    {t('dashboard.assignments.modals.edit.form.solution_hint', { defaultValue: 'Shown to learners only once unlocked' })}
                </p>
            </div>

            <div className="rounded-xl border border-gray-100 bg-white nice-shadow overflow-hidden">
                <div className="p-3 space-y-3">
                    <textarea
                        value={solution}
                        onChange={(e) => onSolutionChange(e.target.value)}
                        rows={4}
                        placeholder={t('dashboard.assignments.modals.edit.form.solution_placeholder', {
                            defaultValue: 'Write the worked solution learners should compare their work against…',
                        })}
                        className={textareaClass}
                    />

                    {/* Attached corrigé document */}
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                            <Paperclip size={14} className="text-gray-400 flex-none" />
                            {stagedFile ? (
                                <p className="text-[11px] font-semibold text-gray-700 truncate">
                                    {stagedFile.name}
                                </p>
                            ) : currentFileName ? (
                                <p className="text-[11px] font-semibold text-gray-700 truncate">
                                    {currentFileName}
                                </p>
                            ) : (
                                <p className="text-[11px] text-gray-400">
                                    {t('dashboard.assignments.modals.edit.form.solution_no_file', { defaultValue: 'No document attached' })}
                                </p>
                            )}
                        </div>
                        <div className="flex items-center gap-1.5 flex-none">
                            {(stagedFile || currentFileName) && (
                                <button
                                    type="button"
                                    onClick={onRemoveFile}
                                    className="inline-flex items-center gap-1 h-7 px-2 rounded-md text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 hover:bg-rose-100 transition-colors"
                                >
                                    <Trash2 size={12} />
                                    {t('dashboard.assignments.modals.edit.form.solution_remove_file', { defaultValue: 'Remove' })}
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className="inline-flex items-center gap-1 h-7 px-2 rounded-md text-[10px] font-bold uppercase tracking-wider text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
                            >
                                <Upload size={12} />
                                {t('dashboard.assignments.modals.edit.form.solution_upload_file', { defaultValue: 'Attach' })}
                            </button>
                            <input
                                ref={fileInputRef}
                                type="file"
                                className="hidden"
                                onChange={(e) => {
                                    const f = e.target.files?.[0];
                                    if (f) onStageFile(f);
                                    // Reset so re-picking the same file still fires onChange.
                                    e.target.value = '';
                                }}
                            />
                        </div>
                    </div>
                </div>

                {/* Reveal rule */}
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50 space-y-2">
                    <p className="text-[11px] font-semibold text-gray-700">
                        {t('dashboard.assignments.modals.edit.form.solution_reveal_label', { defaultValue: 'Unlock the model answer' })}
                    </p>
                    <div className={`grid gap-2 ${revealOptions.length === 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
                        {revealOptions.map((opt) => {
                            const isSelected = effectiveReveal === opt.value;
                            return (
                                <button
                                    key={opt.value}
                                    type="button"
                                    onClick={() => onRevealChange(opt.value)}
                                    className={`flex flex-col items-start gap-1 p-2.5 rounded-lg border text-start transition-colors ${
                                        isSelected
                                            ? 'bg-teal-50 border-teal-300'
                                            : 'bg-white border-gray-200 hover:bg-gray-50'
                                    }`}
                                >
                                    <span className={isSelected ? 'text-teal-600' : 'text-gray-400'}>
                                        {opt.icon}
                                    </span>
                                    <span className={`text-[11px] font-bold ${isSelected ? 'text-gray-900' : 'text-gray-600'}`}>
                                        {opt.label}
                                    </span>
                                    <span className="text-[10px] text-gray-400 leading-tight">{opt.hint}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

function ToggleRow({
    icon,
    label,
    description,
    checked,
    disabled,
    onChange,
    warning,
}: {
    icon: React.ReactNode;
    label: string;
    description: string;
    checked: boolean;
    disabled?: boolean;
    onChange: (_next: boolean) => void;
    warning?: boolean;
}) {
    return (
        <div className={`flex items-start justify-between gap-3 p-3 rounded-xl border nice-shadow ${
            disabled ? 'bg-gray-50 border-gray-100' : 'bg-white border-gray-100'
        }`}>
            <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <div className="mt-0.5 flex-none">{icon}</div>
                <div className="flex flex-col min-w-0">
                    <div className="flex items-center gap-2">
                        <p className="text-xs font-bold text-gray-900">{label}</p>
                        {warning && (
                            <AlertTriangle size={12} className="text-amber-500 flex-none" />
                        )}
                    </div>
                    <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                        {description}
                    </p>
                </div>
            </div>
            <button
                type="button"
                onClick={() => !disabled && onChange(!checked)}
                disabled={disabled}
                aria-pressed={checked}
                className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    disabled
                        ? 'bg-gray-200 cursor-not-allowed'
                        : checked
                            ? 'bg-gray-900'
                            : 'bg-gray-200 hover:bg-gray-300'
                }`}
            >
                <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                        checked ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                    }`}
                />
            </button>
        </div>
    );
}

// Require a locked-down Safe Exam Browser session to submit this assignment.
// The toggle here only flips the DB flag — real enforcement happens
// server-side on every submission-mutating request (see
// _enforce_seb_if_required in the assignments service). The .seb config file
// is only worth downloading once this has actually been SAVED with the
// toggle on: downloading it while the toggle is checked but unsaved would
// hand a student a file whose lockdown isn't enforced yet.
function SEBRow({
    checked,
    onChange,
    quitPassword,
    onQuitPasswordChange,
    savedEnabled,
    onDownload,
    isDownloading,
}: {
    checked: boolean;
    onChange: (_next: boolean) => void;
    quitPassword: string;
    onQuitPasswordChange: (_v: string) => void;
    savedEnabled: boolean;
    onDownload: () => void;
    isDownloading: boolean;
}) {
    const { t } = useTranslation();
    return (
        <div className="rounded-xl border nice-shadow bg-white border-gray-100 overflow-hidden">
            <div className="flex items-start justify-between gap-3 p-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <div className="mt-0.5 flex-none">
                        <ShieldCheck size={16} className="text-rose-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <p className="text-xs font-bold text-gray-900">
                            {t('dashboard.assignments.modals.edit.form.seb_label', { defaultValue: 'Require Safe Exam Browser' })}
                        </p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                            {t('dashboard.assignments.modals.edit.form.seb_description', {
                                defaultValue: 'Learners can only submit from a locked-down Safe Exam Browser session. Requires the current version of SEB on exam machines.',
                            })}
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onChange(!checked)}
                    aria-pressed={checked}
                    className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        checked ? 'bg-gray-900' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                >
                    <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            checked ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                        }`}
                    />
                </button>
            </div>
            {checked && (
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50 space-y-3">
                    <div className="space-y-1.5">
                        <label className="flex items-center gap-1.5 text-[11px] font-semibold text-gray-700">
                            <KeyRound size={12} className="text-gray-400" />
                            {t('dashboard.assignments.modals.edit.form.seb_quit_password_label', { defaultValue: 'Proctor quit password (optional)' })}
                        </label>
                        <input
                            type="text"
                            value={quitPassword}
                            onChange={(e) => onQuitPasswordChange(e.target.value)}
                            placeholder={t('dashboard.assignments.modals.edit.form.seb_quit_password_placeholder', { defaultValue: 'Leave blank to disable' })}
                            className={inputClass}
                        />
                        <p className="text-[10px] text-gray-400 leading-snug">
                            {t('dashboard.assignments.modals.edit.form.seb_quit_password_hint', {
                                defaultValue: "Not needed for the normal flow — students exit automatically once they submit. This is only a proctor's way to force-quit a stuck session.",
                            })}
                        </p>
                    </div>

                    {savedEnabled ? (
                        <button
                            type="button"
                            onClick={onDownload}
                            disabled={isDownloading}
                            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-[11px] font-bold text-gray-700 bg-white border border-gray-200 nice-shadow hover:bg-gray-50 transition-colors disabled:opacity-50"
                        >
                            <Download size={13} />
                            {isDownloading
                                ? t('dashboard.assignments.modals.edit.form.seb_downloading', { defaultValue: 'Preparing…' })
                                : t('dashboard.assignments.modals.edit.form.seb_download', { defaultValue: 'Download .seb config' })}
                        </button>
                    ) : (
                        <p className="text-[10px] text-amber-600 leading-snug">
                            {t('dashboard.assignments.modals.edit.form.seb_save_first', {
                                defaultValue: 'Save this assignment with the toggle on before downloading — the config file only locks down students once this is saved.',
                            })}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

// Restrict submission to a campus network. The toggle + text field here only
// write the DB fields — real enforcement happens server-side on every
// submission-mutating request (see _enforce_ip_allowlist_if_required in the
// assignments service, which fails CLOSED if the toggle is on but the list
// is empty or unparseable, so a misconfiguration blocks everyone rather than
// silently letting them through).
function IpAllowlistRow({
    checked,
    onChange,
    allowlist,
    onAllowlistChange,
}: {
    checked: boolean;
    onChange: (_next: boolean) => void;
    allowlist: string;
    onAllowlistChange: (_v: string) => void;
}) {
    const { t } = useTranslation();
    return (
        <div className="rounded-xl border nice-shadow bg-white border-gray-100 overflow-hidden">
            <div className="flex items-start justify-between gap-3 p-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <div className="mt-0.5 flex-none">
                        <Wifi size={16} className="text-teal-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <p className="text-xs font-bold text-gray-900">
                            {t('dashboard.assignments.modals.edit.form.ip_allowlist_label', { defaultValue: 'Restrict to campus network' })}
                        </p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                            {t('dashboard.assignments.modals.edit.form.ip_allowlist_description', {
                                defaultValue: 'Learners can only submit from an IP address in the list below, e.g. a campus lab or Wi-Fi range.',
                            })}
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onChange(!checked)}
                    aria-pressed={checked}
                    className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        checked ? 'bg-gray-900' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                >
                    <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            checked ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                        }`}
                    />
                </button>
            </div>
            {checked && (
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50 space-y-1.5">
                    <label className="text-[11px] font-semibold text-gray-700">
                        {t('dashboard.assignments.modals.edit.form.ip_allowlist_input_label', { defaultValue: 'Allowed IPs / ranges (one per line)' })}
                    </label>
                    <textarea
                        value={allowlist}
                        onChange={(e) => onAllowlistChange(e.target.value)}
                        placeholder={'203.0.113.0/24\n198.51.100.7'}
                        rows={3}
                        className={`${textareaClass} font-mono text-xs`}
                    />
                    <p className="text-[10px] text-gray-400 leading-snug">
                        {t('dashboard.assignments.modals.edit.form.ip_allowlist_hint', {
                            defaultValue: 'One IP or CIDR range per line (commas also work). Ask your IT department for the campus range. An empty list blocks every learner while this is on.',
                        })}
                    </p>
                </div>
            )}
        </div>
    );
}

// Students self-organize into teams (see AssignmentGroupPanel on the
// student side) sized between minSize and maxSize — either bound optional.
// The toggle here only flips the DB flag; team formation, the shared
// answers, and the single "submit for the whole team" action are all a
// separate, dedicated flow (assignment_groups service + endpoints), not
// something this modal configures further.
function GroupSubmissionRow({
    checked,
    onChange,
    minSize,
    onMinSizeChange,
    maxSize,
    onMaxSizeChange,
}: {
    checked: boolean;
    onChange: (_next: boolean) => void;
    minSize: number | '';
    onMinSizeChange: (_v: number | '') => void;
    maxSize: number | '';
    onMaxSizeChange: (_v: number | '') => void;
}) {
    const { t } = useTranslation();
    return (
        <div className="rounded-xl border nice-shadow bg-white border-gray-100 overflow-hidden">
            <div className="flex items-start justify-between gap-3 p-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <div className="mt-0.5 flex-none">
                        <Users size={16} className="text-indigo-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <p className="text-xs font-bold text-gray-900">
                            {t('dashboard.assignments.modals.edit.form.group_submission_label', { defaultValue: 'Allow team submission' })}
                        </p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                            {t('dashboard.assignments.modals.edit.form.group_submission_description', {
                                defaultValue: 'Learners form their own teams and hand in — and are graded — together, one submission per team.',
                            })}
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onChange(!checked)}
                    aria-pressed={checked}
                    className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        checked ? 'bg-gray-900' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                >
                    <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            checked ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                        }`}
                    />
                </button>
            </div>
            {checked && (
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50">
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-[11px] font-semibold text-gray-700">
                                {t('dashboard.assignments.modals.edit.form.group_min_size_label', { defaultValue: 'Min team size' })}
                            </label>
                            <input
                                type="number"
                                min={1}
                                value={minSize}
                                onChange={(e) => onMinSizeChange(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                                placeholder={t('dashboard.assignments.modals.edit.form.group_size_placeholder', { defaultValue: 'No minimum' })}
                                className={inputClass}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[11px] font-semibold text-gray-700">
                                {t('dashboard.assignments.modals.edit.form.group_max_size_label', { defaultValue: 'Max team size' })}
                            </label>
                            <input
                                type="number"
                                min={1}
                                value={maxSize}
                                onChange={(e) => onMaxSizeChange(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                                placeholder={t('dashboard.assignments.modals.edit.form.group_size_placeholder', { defaultValue: 'No maximum' })}
                                className={inputClass}
                            />
                        </div>
                    </div>
                    <p className="text-[10px] text-gray-400 leading-snug mt-2">
                        {t('dashboard.assignments.modals.edit.form.group_submission_hint', {
                            defaultValue: 'Max size is enforced when joining a team. Min size is shown to students as guidance only — nothing blocks a smaller team from submitting.',
                        })}
                    </p>
                </div>
            )}
        </div>
    );
}

// Per-attempt duration, independent of the due_date deadline above. The
// student sees an explicit "Start attempt" screen and a countdown once
// enabled — see AssignmentTimeLimitGate.tsx — rather than the clock running
// silently from whenever they first open the page.
function TimeLimitRow({
    enabled,
    onEnabledChange,
    minutes,
    onMinutesChange,
}: {
    enabled: boolean;
    onEnabledChange: (_next: boolean) => void;
    minutes: number;
    onMinutesChange: (_next: number) => void;
}) {
    const { t } = useTranslation();
    return (
        <div className="rounded-xl border nice-shadow bg-white border-gray-100 overflow-hidden">
            <div className="flex items-start justify-between gap-3 p-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <div className="mt-0.5 flex-none">
                        <Timer size={16} className="text-amber-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <p className="text-xs font-bold text-gray-900">
                            {t('dashboard.assignments.modals.edit.form.time_limit_label', { defaultValue: 'Time limit' })}
                        </p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                            {t('dashboard.assignments.modals.edit.form.time_limit_description', {
                                defaultValue: 'Learners must explicitly start the attempt; the clock then runs regardless of the due date above.',
                            })}
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onEnabledChange(!enabled)}
                    aria-pressed={enabled}
                    className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        enabled ? 'bg-gray-900' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                >
                    <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            enabled ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                        }`}
                    />
                </button>
            </div>
            {enabled && (
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50">
                    <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] font-semibold text-gray-700">
                            {t('dashboard.assignments.modals.edit.form.time_limit_minutes_label', { defaultValue: 'Minutes' })}
                        </p>
                        <div className="flex-none flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => onMinutesChange(Math.max(1, minutes - 5))}
                                className="h-7 w-7 rounded-md bg-white border border-gray-200 nice-shadow text-gray-600 hover:bg-gray-50 text-sm font-bold"
                            >
                                −
                            </button>
                            <input
                                type="number"
                                min={1}
                                max={600}
                                value={minutes}
                                onChange={(e) => {
                                    const raw = parseInt(e.target.value, 10);
                                    onMinutesChange(isNaN(raw) ? 1 : Math.max(1, Math.min(600, raw)));
                                }}
                                className="w-16 h-7 text-center text-sm font-bold text-gray-900 bg-white border border-gray-200 rounded-md outline-none focus:ring-1 focus:ring-gray-300"
                            />
                            <button
                                type="button"
                                onClick={() => onMinutesChange(Math.min(600, minutes + 5))}
                                className="h-7 w-7 rounded-md bg-white border border-gray-200 nice-shadow text-gray-600 hover:bg-gray-50 text-sm font-bold"
                            >
                                +
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function RetryRow({
    allowRetries,
    maxRetries,
    onAllowChange,
    onMaxChange,
    labelAllow,
    descriptionAllow,
    labelMax,
    helperUnlimited,
    helperBounded,
}: {
    allowRetries: boolean;
    maxRetries: number;
    onAllowChange: (_next: boolean) => void;
    onMaxChange: (_next: number) => void;
    labelAllow: string;
    descriptionAllow: string;
    labelMax: string;
    helperUnlimited: string;
    helperBounded: string;
}) {
    return (
        <div className="rounded-xl border nice-shadow bg-white border-gray-100 overflow-hidden">
            <div className="flex items-start justify-between gap-3 p-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    <div className="mt-0.5 flex-none">
                        <RotateCcw size={16} className="text-fuchsia-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <p className="text-xs font-bold text-gray-900">{labelAllow}</p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">
                            {descriptionAllow}
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onAllowChange(!allowRetries)}
                    aria-pressed={allowRetries}
                    className={`relative flex-none inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        allowRetries ? 'bg-gray-900' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                >
                    <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                            allowRetries ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-1 rtl:-translate-x-1'
                        }`}
                    />
                </button>
            </div>
            {allowRetries && (
                <div className="border-t border-gray-100 px-3 py-3 bg-gray-50/50">
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex flex-col min-w-0">
                            <p className="text-[11px] font-semibold text-gray-700">
                                {labelMax}
                            </p>
                            <p className="text-[10px] text-gray-500 leading-snug mt-0.5 flex items-center gap-1">
                                {maxRetries === 0 ? (
                                    <>
                                        <InfinityIcon size={11} className="text-fuchsia-500" />
                                        <span>{helperUnlimited}</span>
                                    </>
                                ) : (
                                    <span>{helperBounded}</span>
                                )}
                            </p>
                        </div>
                        <div className="flex-none flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() =>
                                    onMaxChange(Math.max(0, (maxRetries || 0) - 1))
                                }
                                className="h-7 w-7 rounded-md bg-white border border-gray-200 nice-shadow text-gray-600 hover:bg-gray-50 text-sm font-bold"
                            >
                                −
                            </button>
                            <input
                                type="number"
                                min={0}
                                max={20}
                                value={maxRetries}
                                onChange={(e) => {
                                    const raw = parseInt(e.target.value, 10);
                                    const clamped = isNaN(raw)
                                        ? 0
                                        : Math.max(0, Math.min(20, raw));
                                    onMaxChange(clamped);
                                }}
                                className="w-12 h-7 text-center text-sm font-bold text-gray-900 bg-white border border-gray-200 rounded-md outline-none focus:ring-1 focus:ring-gray-300"
                            />
                            <button
                                type="button"
                                onClick={() =>
                                    onMaxChange(Math.min(20, (maxRetries || 0) + 1))
                                }
                                className="h-7 w-7 rounded-md bg-white border border-gray-200 nice-shadow text-gray-600 hover:bg-gray-50 text-sm font-bold"
                            >
                                +
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function PassThresholdRow({
    value,
    onChange,
    label,
    description,
    placeholder,
}: {
    value: number | string | null;
    onChange: (_v: number | '') => void;
    label: string;
    description: string;
    placeholder: string;
}) {
    return (
        <div className="rounded-lg border border-gray-200 nice-shadow overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-3 py-2.5">
                <div className="flex items-start gap-2 min-w-0">
                    <Target size={16} className="text-emerald-500 mt-0.5 flex-none" />
                    <div className="flex flex-col min-w-0">
                        <p className="text-[11px] font-semibold text-gray-700">{label}</p>
                        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">{description}</p>
                    </div>
                </div>
                <div className="flex-none flex items-center gap-1.5">
                    <input
                        type="number"
                        min={0}
                        max={100}
                        placeholder={placeholder}
                        value={value === null ? '' : value}
                        onChange={(e) => {
                            const raw = e.target.value;
                            if (raw === '') {
                                onChange('');
                                return;
                            }
                            const parsed = parseInt(raw, 10);
                            onChange(isNaN(parsed) ? '' : Math.max(0, Math.min(100, parsed)));
                        }}
                        className="w-16 h-7 text-center text-sm font-bold text-gray-900 bg-white border border-gray-200 rounded-md outline-none focus:ring-1 focus:ring-gray-300"
                    />
                    <span className="text-xs font-semibold text-gray-400">%</span>
                </div>
            </div>
        </div>
    );
}

export default EditAssignmentModal;
