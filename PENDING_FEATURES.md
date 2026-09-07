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
- Randomized question pools (draw N questions per student from a larger bank).
- Shuffled question/answer order per student (lighter-weight than pooling).
- Webcam proctoring snapshots during a SEB-locked session.
- Campus IP allowlisting for assignment submission, alongside the SEB check.

**Assessment / grading**
- Group/team assignments (`AssignmentUserSubmission` is currently keyed to a
  single user only).
- Peer review workflow (students grade each other's submissions before an
  instructor finalizes).
- Rubric-based grading (multi-criteria weighted scoring, replacing/extending
  the single `grading_type` score).
- Per-student extensions/grace periods on assignment deadlines.
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
