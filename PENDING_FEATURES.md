# Pending / Not Implemented

Tracking doc for everything discussed in the SEB + SCORM work sessions that
is either explicitly out of scope, still needs verification, or was only
brainstormed and never scoped/built. Nothing in this file is started unless
marked otherwise.

## Needs verification in a real environment

Built and `py_compile`/bracket-checked only — this sandbox has no installable
`fastapi`/`sqlmodel`/`defusedxml` and no `node_modules`, so none of this has
run through the project's real test suite, a real DB, or a real browser.

- [ ] Run all three new Alembic migrations against a real Postgres DB:
      `f3a4b5c6d7e8` (SEB fields on `assignment`), `a4b5c6d7e8f9`
      (`scorm_tracking_data`), `b5c6d7e8f9a0` (`time_limit_minutes` on
      `assignment` + `started_at` on `assignmentusersubmission`).
- [ ] Run the actual `pytest` suite (not just the standalone sanity scripts
      used during development).
- [ ] Run a real TypeScript build/typecheck on the web app.
- [ ] Test SEB enforcement against a real Safe Exam Browser client — the
      User-Agent regex and the `allowQuit`/`quitURL` quit flow are spec-correct
      on paper, unverified against actual SEB software.
- [ ] Test SCORM playback against a real exported package (Articulate,
      Captivate, etc.) — only hand-built sample manifests were used to verify
      the parser's edge cases (xml:base, nested items, mastery score, href
      normalization, SCORM 2004 rejection).
- [ ] Test the time-limit flow with real wall-clock timing across a page
      reload/close-and-reopen — the countdown, the auto-submit-on-expiry
      timer, and the server-side check all parse the same naive
      `str(datetime.now())` format independently; worth confirming they
      agree in practice, not just by inspection.

## Repo / workflow governance (blocked on GitHub web UI — can't be done from this session)

- [ ] Set `main` as the repository's default branch
      (Settings → General → Default branch).
- [ ] Add branch protection rules on `main` (require PR before merging,
      require status checks once a workflow has run at least once).
- [ ] Same protection on `dev` if feature branches should PR into it first.
- [ ] Write up the actual workflow in `CONTRIBUTING.md`: feature branch →
      PR into `dev` → tests/staging → PR `dev` → `main`.

(`main` itself has already been created from upstream `learnhouse/learnhouse:main`,
and the feature branch has been rebased onto it — that part is done.)

## Enterprise Edition features — not implemented, and why

`apps/api/ee/` (the actual backend implementation) does not exist in this
repository. This project's own test suite treats that absence as the
expected "OSS build" condition (`pytest.importorskip` / explicit
`pytest.skip("EE not present (OSS build)")` around it) — it is a withheld
commercial deliverable, not an unfinished community feature. None of the
below were built, and building them as literal ports of the withheld module
was declined for that reason.

- **SSO (real IdP integration — SAML/OIDC against an arbitrary school IdP)**.
  Basic auth (password, 2FA, magic links) already exists in OSS; this would
  be genuinely new, from-scratch OSS code, not a port.
- **Payments** — Stripe billing is EE/SaaS only per the README. Nothing to
  build on for a self-host that isn't selling courses.
- **Advanced analytics** — deeper reporting/cohort breakdowns layered on top
  of the analytics that already exist in OSS.
- **Audit logs (advanced tier)** — the OSS foundation already exists
  (`user_audit_event` table, a working router, a dashboard page); the EE gate
  is almost certainly just export/retention/search on top of that.

SCORM was the one EE-listed feature (`EE_ONLY_FEATURES` in
`deployment_mode.py` includes `'scorm'`) that got built anyway, as an
independent OSS implementation — see the main SCORM work already merged.
The manifest-parsing edge cases it handles are properties of the public
SCORM 1.2 / IMS CP spec, not anyone's proprietary logic.

## Additional feature ideas — brainstormed only, none started

Grouped roughly by theme. None of these have been scoped in detail; each
needs its own investigation pass before implementation, same as SEB/SCORM.

**Exam integrity (natural extensions of the SEB work)**
- ~~Per-attempt time limits on assignments~~ — **done.** `time_limit_minutes`
  on `Assignment`, explicit "Start attempt" gate (no silent auto-start),
  server-enforced via `_enforce_time_limit_if_set` on every learner-write
  path, auto-submit on expiry. Needs real-environment verification like
  everything else in this session (see that section above).
- ~~Randomized question pools~~ — **done.** `contents.pool_size` on a QUIZ
  task, no new DB column — same deterministic-per-(user, task, attempt)
  seeding approach as everything else here. Teacher toggle in the quiz task
  editor. Needs real-environment verification like everything else in this
  session.
- ~~Shuffled question/answer order per student~~ — **done.**
  `contents.shuffle_questions` / `shuffle_options` on a QUIZ task, same
  deterministic seed as the pool feature. Genuinely lighter than pooling
  turned out to be true: grading matches answers by UUID, never by
  position, so display-order shuffling needed zero grading-side changes.
- ~~Webcam proctoring snapshots~~ — **done.** Opt-in per assignment
  (`assignment.require_webcam_proctoring`), enforced nowhere — declining the
  frontend consent screen never blocks the attempt. A student who accepts
  gets a persistent on-screen recording indicator and an ~90s-interval JPEG
  frame uploaded to a new `proctoring_snapshot` table; only an instructor
  (RBAC `UPDATE` on the course) can list, view, or bulk-delete a student's
  captured snapshots — a student can never read back their own. Teacher
  toggle in `EditAssignmentModal.tsx`, review gallery in
  `EvaluateAssignment.tsx` (object-URL fetches, since the serve endpoint
  needs a Bearer token a plain `<img src>` can't carry). Needs
  real-environment verification like everything else in this session,
  camera-permission UX across browsers especially.
- ~~Campus IP allowlisting for assignment submission~~ — **done.** Per-assignment
  toggle (`assignment.require_ip_allowlist`) plus a free-text
  `ip_allowlist` field (newline/comma-separated IPs and CIDR ranges).
  Enforced at the same 5 submission-mutating call sites as the SEB/time-limit
  checks, with the same instructor/token exemptions; client IP resolution
  reuses the already-vetted `get_client_ip` from the rate-limiting service
  rather than a second implementation. Fails CLOSED on misconfiguration — an
  empty or unparseable list blocks every non-exempt request rather than
  silently letting everyone through. Teacher toggle + textarea in
  `EditAssignmentModal.tsx`, student-facing blocking screen
  (`AssignmentIpAllowlistGate.tsx`, wrapping the SEB gate) shows the
  student's own resolved IP so they can relay it to campus IT. Needs
  real-environment verification like everything else in this session —
  especially the trusted-proxy IP resolution behind whatever reverse proxy
  a real deployment sits behind.

**Assessment / grading**
- ~~Group/team assignments~~ — **done**, with a deliberate architectural choice
  worth calling out. `AssignmentUserSubmission`/`AssignmentTaskSubmission`
  stay keyed to a single user — restructuring them to be group-keyed would
  touch grading, certificates, the activity trail, and analytics everywhere
  they read those tables, for a self-hosted college's actual need (a team
  hands in once and is graded once). Instead: new `AssignmentGroup` /
  `AssignmentGroupMember` tables track self-formed teams (`allow_group_submission`,
  `group_min_size`/`group_max_size` on the assignment), and every per-user row
  is kept in sync by fan-out at three points — every task-answer autosave
  copies to teammates' own rows (skipping a teammate whose row is already
  locked in), a new "submit for the whole team" endpoint syncs once more then
  advances every member's own submission via the existing single-user
  `create_assignment_submission` (reused unmodified, with a new
  `skip_environment_checks` flag for the teammates who aren't at the
  submitting student's machine — SEB/IP/time-limit are checked once, for
  real, against the actual submitter), and a new "grade whole team" endpoint
  applies one grade + feedback to every member by looping the existing
  `_apply_grade_and_finalize` primitive (already documented as safe for
  multiple callers). A member who can't be advanced/graded (not enrolled,
  nothing submitted yet) is skipped and reported rather than failing the
  whole team. Student UI: `AssignmentGroupPanel.tsx` (create/join/leave/
  submit-for-team, shown alongside the assignment, not gating it). Instructor
  UI: team size toggle in `EditAssignmentModal.tsx`, "Grade whole team"
  button in `EvaluateAssignment.tsx`. NOT enforced: `group_min_size` is
  guidance only, nothing blocks a smaller team from submitting. Needs
  real-environment verification like everything else in this session, this
  one especially — it's the largest change to the submission write path of
  anything built this session, and the recursive `create_assignment_submission`
  reuse in particular has not run against a real database.
- ~~Peer review workflow~~ — **done.** New `PeerReview` table (one row per
  (reviewer, target) pair) plus `assignment.enable_peer_review` /
  `peer_reviews_per_submission`. Instructor triggers "Assign peer reviews"
  (submissions page) once enough students have submitted — a shuffled
  circular assignment hands each submitted learner N classmates' work to
  review, idempotent on re-run (only creates new pairs). Identity anonymity
  is hard-coded, not configurable, in BOTH directions: a reviewer never
  learns whose work they're grading, and a reviewee never learns who
  reviewed them, even after the fact — only the instructor ever sees both
  sides (`PeerReviewSummaryPanel.tsx` in the grading UI). Peer scores are
  purely advisory: nothing here ever writes to the actual grade, which
  stays entirely the instructor's own action. Student UI:
  `AssignmentPeerReviewPanel.tsx` (review queue + a modal to view the
  target's answers and submit score/feedback; the answer rendering is
  generic JSON-ish text, not per-task-type polish — reusing the real
  TaskXxxObject components in a dedicated read-only mode is a follow-up, not
  done here). A reviewee's feedback stays hidden until every assigned
  review of their submission is complete, to prevent inferring authorship
  from a partial reveal. Needs real-environment verification like
  everything else this session.
- ~~Rubric-based grading~~ — **done**, as an optional per-task overlay rather
  than a replacement for the existing single-number grade. A task's rubric
  (a list of `{criterion_uuid, title, description, max_points}`) lives in
  its own `contents["rubric"]` — the same no-migration opaque-JSON pattern
  every other per-task config (pool_size, shuffle_questions,
  response_type) already uses. Grading writes per-criterion points to a new
  `AssignmentTaskSubmission.rubric_scores` JSON column; the task's normal
  0-100 `grade` is DERIVED from those server-side
  (`services.courses.activities.rubric.compute_rubric_grade`, clamped per
  criterion) rather than trusted from the client — same "server verifies"
  treatment every other scored task type gets — which means every existing
  downstream consumer (aggregate grading, certificates, the activity trail)
  keeps reading the same `grade` column it always has, completely unaware a
  rubric was involved. Teacher UI: a new "Rubric" tab in the task editor.
  Grading UI: `RubricGradingWidget.tsx`, a click-to-score overlay wired into
  `AssignmentBoxUI` (the shared grading-controls component) that
  auto-fills the plain grade input — grading without touching it still
  works exactly as before. SCOPE LIMIT: the widget is only wired into
  `TaskFileObject.tsx` (FILE_SUBMISSION, the most common manually-graded
  type) in this pass; `AssignmentBoxUI`'s prop contract supports every
  other type too (`gradeCustomFC`'s type change is backward-compatible), so
  wiring CODE/SHORT_ANSWER/NUMBER_ANSWER/FORM in is a small follow-up, not
  a redesign. Needs real-environment verification like everything else this
  session.
- ~~Per-student extensions/grace periods~~ — **done.** New `AssignmentExtension`
  table (one row per (assignment, student)) whose `extended_due_date`
  REPLACES `assignment.due_date` for that student outright — not just a
  later date, so the same mechanism also covers a legitimate earlier
  individual deadline (an accommodation, or fixing a mistaken extension).
  `_is_assignment_past_due` was split into a pure `_is_date_past(raw)` plus
  a new async `_is_assignment_past_due_for_user(assignment, user_id,
  db_session)` that resolves the effective per-student deadline first; all
  6 deadline gates in the assignments service (file upload, task-answer
  save, submit-for-grading, start-attempt, group-submit, retry) were
  migrated to the per-user form. Group submission gets this for free: since
  `submit_group_assignment` already re-checks the deadline per teammate
  when it calls `create_assignment_submission` for each one, every group
  member's own extension is automatically honored with no group-specific
  code. `AssignmentRead` gained `effective_due_date`, populated only for a
  real learner reader (never an instructor, who needs the plain
  `due_date` to manage the assignment) — the student activity view prefers
  it over `due_date` so an extended student sees their actual deadline.
  Instructor UI: a compact "extend" button per submission row
  (`AssignmentSubmissionsSubPage.tsx`) to grant/revoke one student's
  extension. Needs real-environment verification like everything else this
  session.
- ~~Plagiarism/similarity check~~ — **done**, as in-house cross-submission
  similarity (no third-party API — this is a self-hosted deployment with no
  assumed network egress to Turnitin/Copyleaks/etc.), distinct from the
  existing `anti_copy_paste` UI deterrent (that blocks paste events while a
  student is answering; this compares finished submissions to each other
  afterward). Instructor-triggered ("Run plagiarism check" on the
  submissions page, mirroring "Assign peer reviews"): k-shingle Jaccard
  similarity over CODE (`source_code`) and SHORT_ANSWER (`answer`) task
  submissions, pairwise across every student who submitted, flagged at
  `assignment.plagiarism_similarity_threshold` (default 70%) and stored in
  a new `PlagiarismMatch` table, fully recomputed each run. Never touches a
  grade — purely a review aid the instructor still has to judge.
  KNOWN LIMITATIONS, called out directly rather than left implicit: (1)
  FALSE POSITIVES — a narrow-answer SHORT_ANSWER task (e.g. a single-fact
  question) will show high similarity between every student who simply got
  it right; a length floor (`_MIN_TOKENS_FOR_COMPARISON`) filters the
  shortest cases but doesn't eliminate this for longer narrow-answer tasks.
  (2) EASILY DEFEATED — plain token-shingle similarity is sensitive to
  identifier renaming; a plagiarist who search-replaces variable names in
  copied code will show markedly lower similarity even though the logic is
  identical. (3) FILE_SUBMISSION is NOT covered — the submitted content is
  a binary/document reference, not inline text this can shingle without a
  separate text-extraction pipeline. (4) O(n²) pairwise comparison per
  task — fine at a self-hosted college's classroom scale, not built for a
  MOOC-sized cohort. Needs real-environment verification like everything
  else this session.
- ~~Student-flaggable quiz questions~~ — **done, scoped to the ungraded
  in-content `blockQuiz` self-check block only** — the separate graded
  ASSIGNMENT quiz task type has a different question shape entirely
  (`services/ai/quiz.py`) and is not covered. A quiz question is not its
  own database row (it lives inside a `blockQuiz` node in an activity's
  Prosemirror content document), so `QuizQuestionFlag` references it by
  `(activity_id, quiz_id, question_id)` and keeps a text SNAPSHOT of the
  question at flag time — content can be edited or the block deleted after
  a flag is raised, and the review queue must show what the student
  actually saw, not whatever the block currently contains. A small flag
  icon on each question in read/take mode (never shown in the editor's own
  edit mode) opens an inline reason picker (wrong answer key / unclear
  wording / typo / other) plus an optional note; a repeat flag from the
  same student on the same still-open question is idempotent (returns the
  existing row rather than duplicating), and a per-student, per-course cap
  of 50 open flags backstops against flooding the queue. A new "Flagged
  Questions" course-dashboard tab is the instructor review queue: reason,
  question snapshot, note, who flagged it, and a link back into the
  activity editor, with Resolve/Dismiss actions. `flagged_by`/
  `resolved_by` are `SET NULL` on user deletion rather than cascading —
  the flag stays useful as a content-quality signal even after the person
  who raised or resolved it is gone. Needs real-environment verification
  like everything else this session; the question-lookup and
  idempotent-flag logic were verified with a standalone script against
  synthetic Prosemirror documents (this sandbox has neither `fastapi` nor
  a real DB to exercise the endpoints end-to-end).

**Operations / integration**
- ~~Bulk roster import (CSV) + gradebook export (CSV)~~ — **done.** New
  "Roster" tab on the course dashboard. Import: upload a CSV (an "email"
  column, or a bare single-column list) — every email that already
  resolves to an org member is enrolled immediately (a `Trail`/`TrailRun`
  row, the same thing self-service enrollment writes); every other
  well-formed email is invited to the ORGANIZATION via the existing,
  already-hardened batch-invite flow (`invite_batch_users`) rather than a
  new invite mechanism — there is deliberately no "pending course
  enrollment for an email with no account yet" concept, so the admin
  re-runs the import once an invited student has signed up. Export: one
  CSV row per enrolled student, one column per assignment, reusing the
  exact `display_grade` every other grading surface already computes
  (`read_assignment_submissions`) rather than re-deriving grades. Needs
  real-environment verification like everything else this session,
  especially the invite-then-reimport flow.
- ~~LTI (Learning Tools Interoperability) support~~ — **done, narrowly
  scoped.** LearnHouse as an LTI **Tool Provider** only: a course can be
  launched FROM another LMS (Canvas, Moodle, Blackboard, ...). The reverse
  direction (LearnHouse embedding some other LMS's tool as a Tool
  *Consumer*) is NOT built. Protocol version is **LTI 1.1** (OAuth 1.0a
  HMAC-SHA1-signed launch POST) rather than the newer LTI Advantage 1.3
  (OIDC + JWT + a services ecosystem) — 1.1 is what the large majority of
  existing campus LMS deployments still speak for a basic launch, and it
  avoids standing up a JWKS endpoint or an OIDC login-initiation flow for a
  first integration. Hand-rolled OAuth 1.0a signing (`services/lti/oauth1.py`),
  verified against the canonical RFC 5849 / OAuth 1.0 worked example
  (HMAC-SHA1 of a known base string reproduces the spec's published
  signature exactly) rather than adding an `oauthlib` dependency for one
  signature check. An instructor creates an `LTILink` per course (its own
  random consumer key + secret, secret encrypted at rest via the existing
  webhook-secret Fernet helper) from a new "LTI" course-dashboard tab, and
  pastes the resulting launch URL/key/secret into the external LMS's tool
  config. A launch: verifies the signature over the exact URL it was POSTed
  to, rejects a stale timestamp or a replayed nonce (deduped in Redis,
  fails open to timestamp-only checking if Redis is down), finds-or-creates
  a LearnHouse account for the external LMS's `user_id` (matching an
  existing org member by email first if one is given; otherwise
  provisioning a new account, with a synthetic `@lti.invalid` placeholder
  address — RFC 2606's reserved-for-exactly-this TLD — when the launch
  didn't include one, which many LMS tool configs don't by default),
  enrolls it in the link's course (the same `Trail`/`TrailRun` primitive
  every other enrollment path uses), and redirects the browser to the
  course page with a freshly minted session. A new `lti` session-provenance
  method is exempt from an org's member-facing "allowed sign-in methods"
  policy, same as `api_token` — the `LTILink` itself is the opt-in, not a
  choice a member makes from a login page. KNOWN LIMITATIONS, disclosed in
  the service module's own comments: (1) the launch-to-redirect cookies are
  set `SameSite=None` rather than the app's usual `lax`, which is
  structurally required for a session to survive landing from a
  cross-origin LMS-initiated POST — not a new forgery surface, since the
  launch was already OAuth-signature-authenticated before any cookie is
  set; (2) an account with 2FA enabled cannot complete an LTI launch (there
  is no channel to prompt for a TOTP code inside an LMS-embedded launch) —
  it gets a 409 telling it to sign in directly instead; (3) no Tool
  Consumer direction, no LTI Advantage/1.3, no Deep Linking, no grade
  passback (Outcomes) to the external LMS. Needs real-environment
  verification like everything else this session, especially an actual
  launch from a real Canvas/Moodle sandbox rather than just the
  signature-math self-test this session could run.
- ~~Question-bank import (QTI format)~~ — **done, narrowly scoped.** QTI
  **1.2** only (the classic `<questestinterop>` XML most legacy quiz tools —
  Canvas's QTI export, Blackboard, ExamView, Respondus — still produce),
  NOT the structurally different QTI 2.x/3.x schema. Item types: multiple-
  choice (single- and select-all-that-apply) and true/false, which is just
  a two-option multiple-choice under the hood; essay, short-answer/
  fill-in-blank, matching, and ordering items are recognised and SKIPPED
  (reported back by item identifier and reason) rather than silently
  dropped or guessed at. A new "QTI Import" course-dashboard tab accepts a
  single QTI XML file or a zip of several (an IMS Content Package's
  per-item XML files); the parser is namespace-agnostic local-tag matching
  (mirroring the existing SCORM importer's approach to the same
  inconsistently-namespaced-export problem) over `defusedxml` (XXE
  protection, also matching the SCORM importer) rather than a new XML
  convention. "Correct answer" detection follows the conventional QTI 1.2
  authoring pattern every major exporter uses: a `<respcondition>` marks
  its referenced choice(s) correct when it awards a positive `SCORE` via
  `<setvar>` — verified against hand-built single-response,
  select-all-that-apply, true/false, and essay-should-skip fixtures
  exercising that logic directly (this session's sandbox has neither
  `defusedxml` nor `fastapi` installed, so the parsing/scoring functions
  were verified with the stdlib `xml.etree.ElementTree` swapped in — an
  API-compatible drop-in for everything exercised — rather than skipped).
  A successful import creates ONE NEW activity (a custom content page
  holding a single quiz block with every parsed question) in the chapter
  the instructor picks, reusing the exact `blockQuiz` shape the AI quiz
  generator already produces (`services/ai/quiz.py`'s `_to_block_quiz`) —
  so an imported quiz is indistinguishable from a hand-authored or
  AI-generated one once it lands in the editor, immediately reviewable/
  editable before publishing. There is no separate "question bank" store
  independent of course content; importing IS authoring a quiz activity.
  KNOWN LIMITATIONS: (1) no partial-credit/weighted scoring is imported —
  every question is pass/fail correct-or-not, matching the editor's own
  quiz block, which has no notion of partial credit either; (2) item
  metadata beyond the question/answer text (point values, feedback text,
  images/attachments referenced by `<matimage>`) is discarded; (3) no Tool
  Consumer-style export in the other direction (LearnHouse cannot produce
  a QTI file from its own quizzes). Needs real-environment verification
  like everything else this session, especially against a real QTI 1.2
  export from Canvas/Blackboard/Respondus rather than just the synthetic
  fixtures this session could build.
- ~~Calendar/ICS feed of assignment due dates~~ — **done.** Per-user opaque
  token (`GET /users/me/calendar_feed_token`, regenerable) that stands in
  for authentication on `GET /calendar/feed/{token}.ics` — deliberately the
  only unauthenticated endpoint added this session, since a calendar app
  polls a subscribed URL on its own schedule with no way to carry a
  session Bearer token (the same trust model Canvas/Moodle use for their
  own feeds). Lists every assignment due date across every course the
  user has a `Trail`/`TrailRun` for (i.e. is enrolled in), using each
  student's OWN effective due date (their extension if they have one —
  nice free tie-in with the per-student-extensions feature). Hand-rolled
  ICS output (VEVENT/escaping/RFC 5545 line folding), no external
  `icalendar` dependency assumed. KNOWN LIMITATION, disclosed in the
  service module's own docstring: due dates are emitted as "floating"
  ICS times (no timezone), which is correct for a single-institution
  deployment where students and the deadline share a timezone, but would
  show a mismatched time in a multi-timezone deployment — there is no
  per-org timezone setting to fix this properly. Settings UI: a "Calendar
  feed" panel on the account page (copy/regenerate). Needs
  real-environment verification like everything else this session,
  especially against real calendar clients (Google/Outlook/Apple) rather
  than just RFC-shape checks.
- ~~Anonymous/pseudonymous question posting in course discussions~~ —
  **done.** A "Post anonymously" checkbox on both discussion creation
  (`CreateDiscussionModal`) and comment/reply creation (`CommentSection`).
  `is_anonymous` is stored on the `Discussion`/`DiscussionComment` row
  itself — the real `author_id` is ALWAYS written to the database; nothing
  is anonymized at rest, only redacted on read. Redaction
  (`_resolve_author_for_reader` in `services/communities/discussions.py`,
  inlined equivalently in `comments.py`) always nulls `author` AND
  `author_id` together for every reader except the real author and any
  org admin/maintainer — never a partial reveal, since a bare `author_id`
  integer would be enough to de-anonymize someone via the user-lookup
  endpoint. `is_anonymous` is write-once at creation (not on the `Update`
  models), so a post can't be retroactively laundered as anonymous after
  the fact, nor un-anonymized by its author to hide the switch. List reads
  (`get_discussions_by_community`, `get_comments_by_discussion`) compute
  the admin-status check ONCE per page, not once per row. Frontend:
  `DiscussionCard`/`CommentCard` render "Anonymous" explicitly when
  `is_anonymous` is set and `author` is null, instead of falling through to
  the generic "unknown user" string, which would otherwise read as a data
  error rather than a deliberate choice. KNOWN LIMITATION: no i18n strings
  added to the non-English locale files for the new UI text (uses
  `t(key, { defaultValue })` so it degrades to English rather than showing
  a raw key). Needs real-environment verification like everything else
  this session, especially that an org admin viewing an anonymous post
  really does see the true author (and that nobody else does).

**Retention / engagement**
- At-risk student dashboard (login gaps, multiple failing assignments,
  falling behind pace) for advisors/instructors — distinct from the existing
  per-course analytics.
- Verifiable digital credentials for certificates (Open Badges or a signed
  PDF), extending the certificates that already exist.
- Weekly digest email ("here's what's due, what you haven't started"),
  student-facing — distinct from the existing org-admin lifecycle nudges
  (`services/email/nudge_translations`), which only address admins.
- Gamification (points, streaks, badges for consistent participation) —
  genuinely absent today; worth weighing carefully for a college audience,
  since it fits some course types far better than others.

**Access / scale**
- Offline-capable course content (PWA + service worker caching), so a
  student on unreliable campus wifi or at home can still read cached
  lecture material. No such capability exists today.
- Live video conferencing / virtual classroom (embedded Zoom/Meet, or a
  native WebRTC session) — Boards and Podcasts exist for collaboration and
  async audio; nothing covers a live class session.
- Learning path / prerequisite enforcement (a course or activity stays
  locked until a prior one is completed) — sequencing beyond the existing
  chapter order.
- Native mobile app wrapper (iOS/Android) — large, long-term scope; only
  worth it once the web app's mobile experience is confirmed insufficient
  on its own.

## Small cleanup items

- [ ] `seb-integration-discussion.md` at the repo root is a leftover draft
      from an earlier (now abandoned) plan to post this work as an upstream
      Discussion — irrelevant to the self-host deployment now, safe to delete.
- [ ] No `pytest` test file exists for the SCORM manifest parser/service yet
      (SEB got `test_seb_service.py`; SCORM only has the throwaway sanity
      scripts used during development, never committed as real tests).
