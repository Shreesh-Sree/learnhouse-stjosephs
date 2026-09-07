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
- Pluggable plagiarism/similarity check (third-party API or in-house
  cross-submission similarity), distinct from the existing `anti_copy_paste`
  UI deterrent.
- Student-flaggable quiz questions ("something's wrong with this question")
  feeding an instructor review queue.

**Operations / integration**
- Bulk roster import (CSV) + gradebook export (CSV) for onboarding/offboarding
  a semester's students and handing grades to a registrar/SIS.
- LTI (Learning Tools Interoperability) support, to embed LearnHouse content
  inside another LMS a college already runs, or vice versa.
- Question-bank import (QTI format) for migrating existing quiz content from
  other tools.
- Calendar/ICS feed of assignment due dates.
- Anonymous/pseudonymous question posting in course discussions — visible as
  anonymous to classmates but still identified to the instructor (so it
  can't be abused). Real, well-documented pain point in large lecture
  courses: a lot of students won't ask a "dumb" question under their real
  name, so it never gets asked or answered for anyone.

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
