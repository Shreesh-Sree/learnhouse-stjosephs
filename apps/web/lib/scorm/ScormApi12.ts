/**
 * SCORM 1.2 Run-Time Environment API shim (window.API).
 *
 * Independent implementation against the public ADL SCORM 1.2 RTE spec —
 * the eight method names, the cmi.core data model subset below, and the
 * numeric error codes are the published standard every SCORM 1.2 package
 * expects, not anyone's proprietary interface.
 *
 * Scope is the cmi.core subset this player actually persists (see
 * ScormTrackingData on the backend): lesson_status, score, lesson_location,
 * suspend_data, session_time. cmi.interactions/objectives are accepted as
 * write targets (so content that touches them doesn't error) but not
 * persisted — this player reports completion and score, not per-question
 * interaction analytics.
 */

export type ScormLessonStatus =
  | 'not_attempted'
  | 'incomplete'
  | 'completed'
  | 'passed'
  | 'failed'
  | 'browsed'

const ERROR = {
  NO_ERROR: '0',
  GENERAL_EXCEPTION: '101',
  INVALID_ARGUMENT: '201',
  ELEMENT_CANNOT_HAVE_CHILDREN: '202',
  ELEMENT_NOT_AN_ARRAY: '203',
  NOT_INITIALIZED: '301',
  NOT_IMPLEMENTED: '401',
  INVALID_SET_VALUE: '402',
  ELEMENT_IS_READ_ONLY: '403',
  ELEMENT_IS_WRITE_ONLY: '404',
  INCORRECT_DATA_TYPE: '405',
} as const

const ERROR_STRINGS: Record<string, string> = {
  [ERROR.NO_ERROR]: 'No error',
  [ERROR.GENERAL_EXCEPTION]: 'General exception',
  [ERROR.INVALID_ARGUMENT]: 'Invalid argument error',
  [ERROR.ELEMENT_CANNOT_HAVE_CHILDREN]: 'Element cannot have children',
  [ERROR.ELEMENT_NOT_AN_ARRAY]: 'Element not an array - cannot have count',
  [ERROR.NOT_INITIALIZED]: 'Not initialized',
  [ERROR.NOT_IMPLEMENTED]: 'Not implemented error',
  [ERROR.INVALID_SET_VALUE]: 'Invalid set value, element is a keyword',
  [ERROR.ELEMENT_IS_READ_ONLY]: 'Element is read only',
  [ERROR.ELEMENT_IS_WRITE_ONLY]: 'Element is write only',
  [ERROR.INCORRECT_DATA_TYPE]: 'Data type mismatch',
}

export interface ScormApi12InitialData {
  lesson_status: ScormLessonStatus
  score_raw: number | null
  score_min: number | null
  score_max: number | null
  lesson_location: string | null
  suspend_data: string | null
  /** "" on a fresh attempt, "resume" when tracking data already exists. */
  entry: '' | 'resume'
  student_id: string
  student_name: string
}

export interface ScormApi12Callbacks {
  /** Fired on LMSCommit and on LMSFinish. Fire-and-forget from the shim's
   * point of view — the caller decides how to persist/report failures. */
  onCommit: (data: {
    lesson_status: ScormLessonStatus
    score_raw: number | null
    score_min: number | null
    score_max: number | null
    lesson_location: string | null
    suspend_data: string | null
    session_time_seconds: number
  }) => void
  /** Fired once, on LMSFinish. */
  onFinish?: () => void
}

const READ_ONLY = new Set([
  'cmi.core.student_id',
  'cmi.core.student_name',
  'cmi.core.credit',
  'cmi.core.entry',
  'cmi.core.total_time',
  'cmi.core.lesson_mode',
  'cmi.launch_data',
  'cmi.comments_from_lms',
])

const WRITE_ONLY = new Set(['cmi.core.exit', 'cmi.core.session_time'])

/** "HH:MM:SS.SS" or "HH:MM:SS", per SCORM 1.2's CMITimespan format. */
function parseSessionTime(value: string): number {
  const match = /^(\d{2,4}):(\d{2}):(\d{2}(?:\.\d+)?)$/.exec(value.trim())
  if (!match) return 0
  const [, h, m, s] = match
  return Math.round(Number(h) * 3600 + Number(m) * 60 + Number(s))
}

export class ScormApi12 {
  private initialized = false
  private finished = false
  private lastError: string = ERROR.NO_ERROR
  private sessionTimeSeconds = 0

  private cmi: {
    lesson_status: ScormLessonStatus
    score_raw: number | null
    score_min: number | null
    score_max: number | null
    lesson_location: string
    suspend_data: string
  }

  constructor(
    private readonly initial: ScormApi12InitialData,
    private readonly callbacks: ScormApi12Callbacks
  ) {
    this.cmi = {
      lesson_status: initial.lesson_status,
      score_raw: initial.score_raw,
      score_min: initial.score_min,
      score_max: initial.score_max,
      lesson_location: initial.lesson_location ?? '',
      suspend_data: initial.suspend_data ?? '',
    }
  }

  LMSInitialize(_param: string): string {
    if (this.initialized) {
      this.lastError = ERROR.GENERAL_EXCEPTION
      return 'false'
    }
    this.initialized = true
    this.lastError = ERROR.NO_ERROR
    return 'true'
  }

  LMSFinish(_param: string): string {
    if (!this.initialized || this.finished) {
      this.lastError = ERROR.GENERAL_EXCEPTION
      return 'false'
    }
    this.finished = true
    this.lastError = ERROR.NO_ERROR
    this.commit()
    this.callbacks.onFinish?.()
    return 'true'
  }

  LMSGetValue(element: string): string {
    if (!this.initialized) {
      this.lastError = ERROR.NOT_INITIALIZED
      return ''
    }
    if (WRITE_ONLY.has(element)) {
      this.lastError = ERROR.ELEMENT_IS_WRITE_ONLY
      return ''
    }

    this.lastError = ERROR.NO_ERROR
    switch (element) {
      case 'cmi.core.student_id':
        return this.initial.student_id
      case 'cmi.core.student_name':
        return this.initial.student_name
      case 'cmi.core.lesson_location':
        return this.cmi.lesson_location
      case 'cmi.core.credit':
        return 'credit'
      case 'cmi.core.lesson_status':
        return this.cmi.lesson_status
      case 'cmi.core.entry':
        return this.initial.entry
      case 'cmi.core.score.raw':
        return this.cmi.score_raw != null ? String(this.cmi.score_raw) : ''
      case 'cmi.core.score.min':
        return this.cmi.score_min != null ? String(this.cmi.score_min) : ''
      case 'cmi.core.score.max':
        return this.cmi.score_max != null ? String(this.cmi.score_max) : ''
      case 'cmi.core.total_time':
        return '00:00:00'
      case 'cmi.core.lesson_mode':
        return 'normal'
      case 'cmi.suspend_data':
        return this.cmi.suspend_data
      case 'cmi.launch_data':
        return ''
      case 'cmi.comments':
        return ''
      case 'cmi.comments_from_lms':
        return ''
      default:
        // cmi.objectives.*, cmi.interactions.* and anything else this
        // player doesn't track: report empty rather than an error so
        // content that merely PROBES these elements (common defensive
        // coding in authoring-tool output) doesn't treat it as fatal.
        return ''
    }
  }

  LMSSetValue(element: string, value: string): string {
    if (!this.initialized) {
      this.lastError = ERROR.NOT_INITIALIZED
      return 'false'
    }
    if (READ_ONLY.has(element)) {
      this.lastError = ERROR.ELEMENT_IS_READ_ONLY
      return 'false'
    }

    this.lastError = ERROR.NO_ERROR
    switch (element) {
      case 'cmi.core.lesson_location':
        this.cmi.lesson_location = value
        return 'true'
      case 'cmi.core.lesson_status':
        this.cmi.lesson_status = value as ScormLessonStatus
        return 'true'
      case 'cmi.core.score.raw':
        this.cmi.score_raw = value === '' ? null : Number(value)
        return 'true'
      case 'cmi.core.score.min':
        this.cmi.score_min = value === '' ? null : Number(value)
        return 'true'
      case 'cmi.core.score.max':
        this.cmi.score_max = value === '' ? null : Number(value)
        return 'true'
      case 'cmi.core.session_time':
        this.sessionTimeSeconds += parseSessionTime(value)
        return 'true'
      case 'cmi.core.exit':
        return 'true' // accepted, not persisted — exit mode doesn't change tracking
      case 'cmi.suspend_data':
        this.cmi.suspend_data = value
        return 'true'
      case 'cmi.comments':
        return 'true'
      default:
        if (element.startsWith('cmi.objectives.') || element.startsWith('cmi.interactions.')) {
          return 'true' // accepted, not persisted — see class docstring
        }
        this.lastError = ERROR.INVALID_ARGUMENT
        return 'false'
    }
  }

  LMSCommit(_param: string): string {
    if (!this.initialized) {
      this.lastError = ERROR.NOT_INITIALIZED
      return 'false'
    }
    this.lastError = ERROR.NO_ERROR
    this.commit()
    return 'true'
  }

  LMSGetLastError(): string {
    return this.lastError
  }

  LMSGetErrorString(errorCode: string): string {
    return ERROR_STRINGS[errorCode] ?? ''
  }

  LMSGetDiagnostic(errorCode: string): string {
    return ERROR_STRINGS[errorCode] ?? ''
  }

  private commit(): void {
    const sessionTime = this.sessionTimeSeconds
    this.sessionTimeSeconds = 0 // each commit reports its OWN session_time; the backend accumulates
    this.callbacks.onCommit({
      lesson_status: this.cmi.lesson_status,
      score_raw: this.cmi.score_raw,
      score_min: this.cmi.score_min,
      score_max: this.cmi.score_max,
      lesson_location: this.cmi.lesson_location || null,
      suspend_data: this.cmi.suspend_data || null,
      session_time_seconds: sessionTime,
    })
  }
}
