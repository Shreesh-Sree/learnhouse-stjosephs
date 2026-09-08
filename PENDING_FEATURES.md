# Pending / Not Implemented

Tracking doc for everything discussed in the SEB + SCORM work sessions that
is either explicitly out of scope, still needs verification, or was only
brainstormed and never scoped/built. Nothing in this file is started unless
marked otherwise.

## Needs verification in a real environment

Originally written when this sandbox had no installable `fastapi`/`sqlmodel`/
`defusedxml`/`node_modules` — everything below was build/bracket-checked only.
That constraint no longer holds: this sandbox turned out to have a real
Postgres 16 cluster and `bun`/`npm` available, just not started/installed.
Backend deps were pip-installed, the DB started and seeded, `node_modules`
installed, and the actual test suites, a real migration run, a real
production build, and a real browser (Playwright against the pre-installed
Chromium) were all run for real. Results below.

- [x] ~~Run all three new Alembic migrations against a real Postgres DB~~
      Done, and more thoroughly than originally scoped: rather than only the
      3 originally-flagged migrations, reverted the DB to the common parent
      revision (`b1c2d3e4f5a6`) and ran the FULL chain forward
      (`alembic upgrade head`, 18 migrations) and back
      (`alembic downgrade b1c2d3e4f5a6`) against real Postgres 16 — every
      upgrade/downgrade pair applied cleanly, and the resulting schema
      (columns, indexes, unique constraints, FKs) matches each migration's
      own definition exactly. Also ran the real fresh-install path
      (`cli.py install --short`, i.e. `SQLModel.metadata.create_all` + admin
      user creation) against the same DB — this is what a real deployment
      actually runs, and it required installing the `pgvector` Postgres
      extension (not documented anywhere — a fresh self-host Postgres
      without it fails on `course_embedding`'s `VECTOR` column; worth adding
      to setup docs).
- [x] ~~Run the actual `pytest` suite~~ Done — installed the full pinned
      dependency set from `pyproject.toml` and ran it for real:
      **5,736 passed, 0 failed, 29 skipped** (the EE-only files, expected).
      Found and fixed 7 real bugs along the way that no amount of reading
      would have caught:
      - `assignments.py` used `Optional` without importing it from `typing`
        — broke collection for 53 test files outright.
      - `nudges.py` had a nested-same-quote f-string
        (`f"...{x or "unknown"}..."`), a `SyntaxError` outside Python 3.12+.
      - 5 test-mock/allowlist gaps: `test_assignment_grading.py` and
        `test_server_verify_dispatch_edge.py`'s `SimpleNamespace` mocks were
        missing `user_id`/`id` that `_server_verified_task_grade` now
        legitimately reads for QUIZ pool-question seeding; and
        `test_demo_teardown.py`'s FK-cascade completeness check didn't know
        `quiz_question_flag`'s two `SET NULL` columns were an intentional
        (not overlooked) choice.
- [x] ~~Run a real TypeScript build/typecheck on the web app~~ Done —
      `bun install` (1038 packages) then `bun run build` (`next build`,
      which typechecks the whole app). First run: 4 real type errors, all
      fixed:
      - `RequestBodyFormWithAuthHeader` required a non-optional
        `access_token: string` and unconditionally sent
        `Authorization: Bearer ${access_token}`; two callers hold a nullable
        token and were passing `access_token || undefined` just to satisfy
        the type — meaning a missing token would have sent the literal
        header `Bearer undefined` instead of omitting it. Fixed the function
        itself to guard this, matching its sibling `RequestBodyWithAuthHeader`.
      - `GroupSubmissionRow`'s `minSize`/`maxSize` props were typed as the
        literal `number | ''`, narrower than the `number | string` TS
        actually infers for the formik values feeding them (empty-string
        literals widen in an untyped object literal) — widened the prop
        types to match.
      Build now exits 0 with zero type errors. Also ran the existing bun
      unit suite (`bun test tests`): one real failure surfaced —
      `ar.json` (Arabic) was missing 24 keys the SEB/quiz-pool/time-limit
      features had added to `en.json` but never localized; added Arabic
      translations for all 24. **263/263 pass now.**
      **Also found — not merely a type nit, a real availability bug**:
      running the actual login flow against a live backend (see the E2E
      item below) surfaced that `check_login_rate_limit` had no fallback
      when Redis is unreachable — `get_redis_connection()` raised
      `HTTPException(500)` outright, and the live Redis calls in
      `check_rate_limit`/`check_invite_rate_limit`/`increment_rate_limit`
      had no `try/except` at all, so a `redis.exceptions.ConnectionError`
      propagated straight up and login/signup 500'd unconditionally.
      Every OTHER Redis-dependent path in this codebase (pack
      reconciliation, the captions consumer) already treats Redis as
      optional and degrades gracefully — this was the one place that
      didn't. Fixed to fail open (log a warning, let the request through
      uncounted) rather than take down login/signup entirely; this matters
      because Redis is genuinely optional in this project's own design
      (`get_redis_client() -> Optional[Redis]`) and plenty of self-host
      deployments won't run it at all.
- [x] Added a Playwright E2E smoke suite
      (`apps/web/playwright.config.ts` + `apps/web/e2e/smoke.spec.ts`,
      `bun run test:e2e`) and ran it for real against a fully live stack:
      real Postgres 16 + a live `uvicorn` backend + `next dev` + the
      sandbox's pre-installed Chromium (pointed at directly via
      `launchOptions.executablePath`, since the default headless_shell
      variant Playwright wants isn't the one preinstalled here). Covers:
      homepage load, the login form rendering, a real password-login round
      trip against the live backend, and an authenticated dashboard view
      loading without erroring. **4/4 pass.** This is what actually
      surfaced the Redis fail-open bug above — the suite was blocked on
      login until that landed. Scope is a smoke suite, not full coverage:
      a fresh install has no seed course/assignment/SCORM content, so
      course creation, submission, and playback flows aren't exercised
      here — a fuller pass would need to seed that content first (e.g.
      extend `cli.py install` or add an E2E fixture script), then add specs
      for: creating a course and publishing an activity, submitting an
      assignment (short-answer/quiz/file), the SEB gate and time-limit
      countdown, and SCORM package upload + playback.
- [ ] Test SEB enforcement against a real Safe Exam Browser client — the
      User-Agent regex and the `allowQuit`/`quitURL` quit flow are spec-correct
      on paper, unverified against actual SEB software. (Nothing in this
      session changed that — SEB itself isn't something a sandbox can run.)
- [ ] Test SCORM playback against a real exported package (Articulate,
      Captivate, etc.) — only hand-built sample manifests were used to verify
      the parser's edge cases (xml:base, nested items, mastery score, href
      normalization, SCORM 2004 rejection). The new
      `test_oss_scorm_service.py` (see Small cleanup items) now runs those
      hand-built cases for real in pytest, but that's still not a real
      Articulate/Captivate export.
- [ ] Test the time-limit flow with real wall-clock timing across a page
      reload/close-and-reopen — the countdown, the auto-submit-on-expiry
      timer, and the server-side check all parse the same naive
      `str(datetime.now())` format independently; worth confirming they
      agree in practice, not just by inspection. (Not covered by the new
      E2E smoke suite — needs a seeded assignment with a time limit set.)

## Bug found and fixed this session: dashboard settings pages, and the SSO gate chain

**Update: root-caused and fixed.** What follows was originally written up as
"every `[subpage]`-style dashboard settings route 404s, needs its own
investigation" — that write-up was wrong about the cause (blamed the app;
it was a testing artifact) and incomplete about the real bug underneath it
(a 5-layer EE-feature gate, only 2 of which had been fixed). Both are now
actually fixed and verified live in a real browser. Keeping the history here
since the misdiagnosis is itself worth learning from.

**What looked like the bug**: `/dash/developers/api`, `/dash/developers/sso`,
`/dash/org/settings/general` all returned a genuine HTTP 404, for every
`[subpage]`-style dashboard route, even a plan/feature-gate-free tab like
`api`. Looked systemic and severe.

**What it actually was**: a self-inflicted testing bug, not an app bug.
`proxy.ts`'s tenant-scoped rewrite (section 11) unconditionally prepends
`/orgs/{slug}` to every incoming pathname, with no guard against a path that
already has that prefix. Every test/manual check in this session (and one
already-committed E2E test, `authenticated session can open the org
dashboard without erroring`) navigated directly to
`/orgs/default/dash/...` — which the proxy then rewrites AGAIN into
`/orgs/default/orgs/default/dash/...`, a route that doesn't exist. The
existing E2E test's assertions (`not.toContainText('Application error'
/'500')`) were too weak to catch this — a 404 page says "404!", not
"Application error" or "500" — so it had been silently passing against a
404 the whole time. Confirmed by navigating to the bare path instead
(`/dash/developers/api`, no `/orgs/{slug}` prefix — every real link in the
app already navigates this way): 200 OK, every time. Fixed the existing
E2E test to use the bare path and assert on the actual response status
(`expect(resp?.status()).toBe(200)`) instead of string-matching.

**The real bug this surfaced**, once the wrong URL was out of the way:
browser-loading the (correctly-routed) SSO settings page showed a "Single
Sign-On (SSO) is a premium feature... Upgrade to Enterprise" paywall card
instead of the real settings form — despite the backend and the
`OSS_BLOCKED_FEATURES` frontend fix (this file, SSO entry below) both being
correct. Five independent layers had to each say "available" for the page
to actually render, and only two had been fixed:
1. Tab visibility in the dashboard nav — `OSS_BLOCKED_FEATURES` in
   `plans.ts` — **already fixed** (SSO entry below).
2. The actual backend `resolve_feature()` function
   (`src/security/features_utils/resolve.py`) — still returned
   `{enabled: false}` for `sso`/`scorm`/`audit_logs` in OSS mode, because
   `EE_ONLY_FEATURES` still lists them (correctly — SaaS-mode plan gating
   needs it) and nothing had special-cased the OSS branch. **Fixed**: added
   `_OSS_BUILT_EE_FEATURES = frozenset({"sso", "scorm", "audit_logs"})`,
   checked in the OSS branch before the `EE_ONLY_FEATURES` block, leaving
   `EE_ONLY_FEATURES`/`plans.py` untouched for SaaS mode. This is the
   function that populates `org.config.config.resolved_features` — the
   single source every frontend `FeatureGate` reads.
3. `OrgEditSSO.tsx`, `OrgAuditLogs.tsx`, and the course page's SCORM upload
   panel all wrap their content in `<FeatureGate feature="...">`, reading
   that `resolved_features` value via `useResolvedFeature`. Once (2) was
   fixed this layer resolved correctly with no further change needed.
4. **The actual deepest bug**: `resolveGateReason()`
   (`lib/features/gateReason.ts`) computes `meetsPlan` by comparing
   `currentPlan` against `required_plan` via `planMeetsRequirement()` —
   completely independently of the backend's `enabled` flag from (2).
   `planMeetsRequirement`'s `'oss'` branch hardcodes
   `return requiredPlan !== 'enterprise'` — i.e. an OSS deployment can
   *never* meet an `'enterprise'`-tier requirement, no matter what the
   backend resolved. Since `sso`/`scorm`/`audit_logs` still carry
   `required_plan: 'enterprise'` (correctly, for SaaS), this silently
   re-blocked the gate even after (2)'s fix. **Fixed**: `meetsPlan` now
   trusts the backend (`resolved.enabled === true`) when `currentPlan ===
   'oss'`, bypassing the static hierarchy check for exactly this case —
   deliberately scoped to OSS mode only, so a SaaS-mode backend/plan
   mismatch still gates (a deliberate defense-in-depth test,
   `tests/feature-gate-lockout.test.mjs`, catches any regression there).
5. `OrgEditSSO.tsx`'s own form logic had two more, separate bugs once the
   gate itself opened: it defaulted to a hardcoded `'workos'` provider (not
   one of the 4 this project actually implements) and sent
   `issuer_url`/`scopes` field names that don't match the backend's real
   `SSOProviderConfigIn` schema (`issuer`/`scope`) — every provider except
   `custom_oidc` would have silently saved an empty config. Fixed: dropped
   the dead WorkOS-only branch, corrected the field names, extended the
   shared OIDC field block to all four real providers, and defaulted the
   dropdown to the first fetched provider instead of an invalid one.

**Verified live, in a real browser, after all five fixes**: the SSO
settings page at `/dash/developers/sso` loads (200, no 404), shows no
paywall card, and renders the real form — provider dropdown populated
from a live `GET /auth/sso/providers` call, defaulted to Keycloak, correct
Issuer URL/Client ID/Client Secret fields. Added as a real regression test
in the E2E smoke suite (`SSO admin settings page reflects the real
backend, not a paywall card`) — 5/5 smoke tests pass. Backend:
`test_feature_resolve.py`/`test_plan_check.py`/`test_feature_dependencies.py`
and the rest of the security/orgs test suite pass unchanged. Frontend:
`bun test tests` 263/263 pass, including the strengthened
`feature-gate-lockout.test.mjs` (which now specifically pins the OSS-vs-SaaS
distinction in the fix). Also browser-verified `OrgAuditLogs.tsx`
(`/dash/users/settings/audit-logs`): no paywall card, real table UI (search/
filter/export/columns), "No logs found" simply because this session's admin
hadn't generated matching events — correct empty state, not a gate.

Also browser-verified the SCORM import panel (`/dash/courses` → "Import
Course" → "SCORM Package"): clicking through live surfaced a sixth, separate
bug beyond the five above. The import button itself was already correctly
enabled — `ImportTypeSelector.tsx` reads `resolved_features.scorm.enabled`
directly, not through `planMeetsRequirement()` — but it rendered a
`<PlanBadge requiredPlan="enterprise">` unconditionally next to the option.
`PlanBadge` decides whether to show via `planMeetsRequirement()`, whose
`'oss'` branch hardcodes `false` for any `'enterprise'` requirement (the same
trap as fix 4 above), so it displayed an "Enterprise" lock badge on a button
that was actually clickable and fully working — misleading, not blocking,
but still a real bug an admin would trust over the UI actually letting them
in. Fixed by only rendering the badge when `!canUseScorm`, i.e. trusting the
already-correct resolved-feature check instead of re-deriving gate state
from the plan tier a second time. Confirmed live: the "Enterprise" badge is
gone and the real "Import SCORM" upload step ("Click to upload or drag and
drop", SCORM 1.2/2004) renders. Added as a permanent regression test,
`SCORM import panel is usable, not gated, in OSS mode` — 6/6 smoke tests
pass.

**Follow-up sweep of the other EE-only features** (`EE_ONLY_FEATURES` in
`src/core/deployment_mode.py`: sso, audit_logs, payments, analytics_advanced,
scorm — all five, not just the three above), done on request after the
SCORM fix. Two more real bugs of the exact same shape turned up by grepping
every remaining `planMeetsRequirement(...)`/`'enterprise'` call site in
`apps/web` and clicking through each hit:

7. **`app/orgs/[orgslug]/dash/analytics/page.tsx`** computed
   `isAdvanced = planMeetsRequirement(plan, 'enterprise')` for the entire
   "Advanced" analytics tab (14 widgets: cohort retention, dropoff map, time
   to completion, etc.). In OSS mode `plan` is the `'oss'` pseudo-plan, and
   `planMeetsRequirement('oss', 'enterprise')` is hardcoded `false` — so the
   whole tab rendered every widget behind `AdvancedGate`'s "Upgrade to
   Enterprise" lock card, even though the backend
   (`src/routers/analytics.py`) already runs every `ADVANCED_QUERIES` query
   unconditionally outside SaaS mode. This is the actual "Advanced
   analytics" feature the user asked to be built in this session — it was
   built and unblocked on the backend, but the frontend gate for it was
   never fixed, so it was invisible the whole time. Fixed:
   `isAdvanced = getDeploymentMode() !== 'saas' || planMeetsRequirement(plan, 'enterprise')`,
   deferring to the plan check only where the backend's gate is real (SaaS).
8. **Two `DashTabBar` tab configs** — the SSO tab in
   `app/orgs/[orgslug]/dash/developers/[subpage]/page.tsx` and the Audit
   Logs tab in `app/orgs/[orgslug]/dash/users/settings/[subpage]/page.tsx` —
   hardcoded `requiredPlan`/`requiresPlan: 'enterprise'` unconditionally.
   `DashTabBar` renders a `PlanBadge` for any tab carrying that field, and
   `PlanBadge` itself decides visibility via the same broken
   `planMeetsRequirement()` call, so both tabs showed an "Enterprise" lock
   badge right on the tab strip even though clicking either one opens a
   fully working page (per fixes 1-6 above) — the tab-bar badge is a
   separate code path from `FeatureGate`/`resolveGateReason` and wasn't
   touched by that earlier fix. Fixed both the same way as the SCORM import
   badge: read `resolved_features.sso.enabled` / `.audit_logs.enabled` and
   only keep the plan requirement when the feature is actually unavailable.

Payments is the one EE-only feature left genuinely gated in OSS mode, and
that's correct, not a bug — see the comment in `services/plans/plans.ts`:
it's real Stripe/billing integration work a self-host that isn't selling
course access publicly doesn't need, and nothing in this session built it.

Verified live for both new fixes: `/dash/developers/sso`,
`/dash/users/settings/audit-logs`, and the Analytics "Advanced" tab all
render with no "Enterprise" text anywhere on the page (checked via full
page-text assertions, not just the specific badge locations). The
Advanced tab correctly still shows an unrelated "Analytics requires a
Tinybird connection" empty state — that's this sandbox having no
`LEARNHOUSE_TINYBIRD_*` env vars configured, a real infra prerequisite,
not a plan gate. Added as a permanent regression test, `SSO tab, Audit
Logs tab, and Advanced analytics tab carry no stray Enterprise badge` —
7/7 smoke tests pass. Frontend unit suite still 263/263, backend
security/orgs + analytics/audit router suites still 1423 passed / 4
skipped (both unaffected — this pass was frontend-only).

## End-to-end feature sweep (this session, on request: "test all the features end to end")

Built a broad Playwright suite (`apps/web/e2e/full-sweep.spec.ts`) covering
every top-level dashboard route reachable from the sidebar — courses,
assignments, library, communities, podcasts, boards, playgrounds, analytics,
every Users-settings subpage, every Org-settings subpage, every Developers
subpage — asserting each returns 200 and renders with no application/server
error, run against the real Postgres + FastAPI + Next.js stack. **29/29
pass** with no gate/paywall regressions found beyond the ones already fixed
earlier in this session.

**The one real bug this pass found — and it's a serious one**: creating a
chapter or activity in the course editor never appeared in the UI without a
full page reload. 100% reproducible, on every single create. Root-caused
through an extensive live debugging session (direct backend curls,
browser-injected debug logging inside `CourseContext.tsx`'s query hook,
manual `fetch()` calls from the page context, request/response tracing) that
initially misdiagnosed this as a `react-query` cache-key mismatch (the
editor's `useQuery` for course metadata uses a different key,
`['course', uuid, 'meta', 'withUnpublished']`, than the canonical
`queryKeys.courses.meta(uuid)` every mutation handler was invalidating) —
a real, separate bug in its own right, fixed by consolidating both onto a
shared `queryKeys.courses.metaWithUnpublished()` key and having every
mutation handler push a directly-fetched fresh response into the cache via
`setQueryData` (`refreshCourseStructureCache` in `services/courses/courses.ts`)
rather than relying on `invalidateQueries` + hoping a background refetch
lands — done in `NewActivityButton.tsx`, `EditCourseStructure.tsx`,
`ChapterElement.tsx`, `ActivityElement.tsx`, `AssignmentActivityModal.tsx`,
and `ActivitySwitcher.tsx`.

That alone didn't fix it. The actual root cause was one layer deeper:
`public/sw.js`, an offline-reading service worker built in an earlier
session (deliberately caching `GET /api/v1/courses|chapters|activities/...`
with a stale-while-revalidate strategy so a student's already-opened lesson
keeps working when campus wifi drops), was intercepting the dashboard
editor's OWN requests too — including ones carrying
`with_unpublished_activities=true`, a parameter only the editor ever sends.
Stale-while-revalidate serves the cached response immediately and updates
the cache in the background, so every GET made immediately after a write
returned the state from BEFORE that write, one request behind, no matter
what triggered it (react-query's own refetch, an explicit manual
`page.evaluate` fetch — every path was equally intercepted since Service
Worker interception happens ahead of the browser's own HTTP cache
semantics, so `cache: 'no-store'` on the fetch init never had a chance to
matter). This is what actually explained the fully reproducible symptom,
and it's why the earlier `refreshCourseStructureCache` fix alone wasn't
sufficient — its own fresh-data fetch was itself served stale by the same
service worker on the very first call after a mutation.

Fixed at the true source: `isCacheableApiRequest()` in `sw.js` now checks
for `with_unpublished_activities=true` in the request URL and always goes
straight to the network for it, leaving the offline-reading cache path
(used only by published-content readers, who never send that flag)
completely untouched — the fix is one `if` statement, precisely scoped to
not regress the offline-reading feature it sits next to.

Verified live end to end: created a throwaway course through the real UI,
added a chapter, watched it render immediately with zero reload, added an
activity under it, watched that render immediately too. Ran the same
create-activity flow 3 times in a row post-fix with zero flakiness (it had
been 100% reproducible pre-fix, every single time, across roughly 15
separate manual repro attempts during diagnosis). Added a permanent
regression test, `creating a chapter and an activity updates the editor
live`, to `full-sweep.spec.ts` — it creates its own throwaway course rather
than depending on seeded data, so it's portable to any environment. Frontend
unit suite still 263/263 (`bun test tests`) after the query-key
consolidation.

### Assignments: two more real bugs, one of them severe

Continuing the sweep into Assignments (create/submit/grade) surfaced two
more genuine, live-verified bugs — the second is arguably the most severe
finding of this whole pass.

1. **The global "New Assignment" flow was a dead end for every course,
   always.** `NewAssignmentModal.tsx` (reached from `/dash/assignments` →
   "New Assignment") called `getCourse()` — a plain `GET courses/{uuid}`
   that returns `CourseRead`, which has no `chapters` field at all — to
   populate the chapter-picker step. Every course showed "This course has
   no chapters yet," even courses that visibly had several, because the
   response object literally never carried that data. Fixed by switching
   to `getCourseMetadata()` (the `/meta` endpoint, `FullCourseRead`, which
   actually returns chapters/activities) with `withUnpublishedActivities:
   true` — an admin placing a new assignment needs to see draft chapters,
   not just published ones.
2. **Creating an assignment, a usergroup, or a podcast 500'd on every
   single attempt in this OSS sandbox (no Redis).** Root-caused via the
   backend log's full traceback: `increase_feature_usage()` in
   `security/features_utils/usage.py` calls `_get_redis_client()` with no
   guard, and that function deliberately raises `HTTPException(500)` when
   Redis is unreachable — the same failure mode as the login-rate-limit
   bug fixed earlier this session, just in a different call site. The
   browser's own console reported this as a CORS error ("No
   'Access-Control-Allow-Origin' header"), which is a red herring: Chrome
   reports a hard 5xx-without-CORS-headers failure that way, and a direct
   curl confirmed the endpoint's CORS headers are correctly present on
   every other response shape (200, 422) — only the unhandled-exception
   500 path was missing them. `increase_feature_usage`/
   `decrease_feature_usage` are called for `assignments`, `usergroups`,
   and `podcasts` (not `courses`/`members`/`admin_seats`, which route
   through a separate Postgres-backed path and were unaffected) — so this
   blocked THREE core creation/deletion flows, not just one, in any
   Redis-less deployment. The usage counter these functions maintain only
   ever feeds SaaS plan-limit enforcement (`resolve_feature()` always
   returns `limit: 0` outside SaaS mode, so the limit check itself is
   already a no-op there) — fixed by skipping the Redis call entirely
   outside SaaS mode, and failing open (log, don't raise) even in SaaS
   mode so a transient Redis outage doesn't take down the caller's actual
   create/delete request over a soft usage counter.

   A related, smaller bug in `AssignmentActivityModal.tsx`'s
   `handleSubmit`: it had no error handling at all around either create
   call or the post-creation cache refresh. A failure at any of those
   points (this Redis crash included) left the submit button stuck in a
   permanently-disabled loading state with the modal never closing —
   confirmed via screenshot mid-diagnosis: the assignment had actually
   been created successfully (visible in the list behind the stuck modal)
   but the user would have no way to tell short of manually closing it.
   Wrapped each step in try/catch: a failure on the create calls now shows
   an error toast and resets the form (with orphan cleanup if the activity
   was created but the assignment record wasn't); a failure in the
   best-effort cache refresh no longer blocks the already-successful
   creation from closing the modal.

   Verified live end to end for both `assignments` and `usergroups`:
   creation now returns 200 (previously 500) and appears immediately.
   Added `test_increase_decrease_feature_usage_skip_redis_outside_saas`
   and `test_increase_decrease_feature_usage_fail_open_on_redis_outage` to
   `test_feature_usage.py`, and updated the 6 existing tests that
   specifically exercise the Redis-tracked path to mock SaaS mode (they
   were asserting Redis calls that, correctly, no longer happen outside
   SaaS mode). Full backend `src/tests/security` + `src/tests/services`
   suite: **4702 passed, 29 skipped, 0 failed** — no regressions from the
   usage.py change reaching any other feature (`courses`, `members`
   tracking is on the separate Postgres path and was never affected).

### Library, Communities, Podcasts, Boards, Playgrounds create flows — all verified working

Continued the sweep through the remaining content-creation areas, live,
through the real UI each time: Library folder creation, Community
creation, Podcast creation (this one specifically to confirm the Redis
usage-tracking fix above — `podcasts` shares the exact same
`increase_feature_usage`/`decrease_feature_usage` code path as
assignments/usergroups; confirmed 200, not 500), Board creation, and
Playground creation. All five worked cleanly on the first try — each new
item appeared immediately in its list with no reload needed and no
console errors, and no further bugs were found in any of them.

### Org general settings save — a required field with nothing to do with what's being saved

`OrgEditGeneral.tsx`'s Yup schema required `label` (a discovery/category
taxonomy field — "Business," "Gaming," "Tech," etc. — `Optional[str]` on
the backend, `OrganizationUpdate.label`) for the entire general-settings
form, meaning **every** save through that form failed with "Organization
label is required" unless a label had already been picked — including
completely unrelated edits like footer text, org description, or default
language. The seeded default org ships with no label set, so this was a
first-save wall for every fresh self-host install: confirmed live by
editing only the footer-text field on a totally fresh org and hitting the
same blocking validation error. Fixed by making the frontend schema match
the backend's own optional contract (`Yup.string().optional()`). Verified
live: saving now round-trips through 4 real `PUT` requests (org name/desc,
footer text, sender name, default language, all 200) and the change
persists across a full page reload. Added a permanent regression test to
`full-sweep.spec.ts`. Frontend build and `bun test tests` (263/263) both
clean.

### Users settings — Sign-in, Two-factor, Roles, Signups & Invite Codes

Continued the sweep into the remaining Users-settings tabs.

**Sign-in and Two-factor both save correctly.** Both write through a
single shared `PUT /auth/mfa/org-policy/{orgId}` endpoint (confirmed by
reading `useOrgSecurityPolicy` in `shared.tsx` — not a bug, a deliberately
shared org-security-policy object covering both concerns despite the
endpoint's MFA-flavored name). Toggling an allowed sign-in method and
saving round-trips a real 200 and persists across a reload. Two-factor's
own save was verified via the safe "exempt Google/SSO users" checkbox
rather than actually flipping "Require two-factor authentication" on —
doing that for real would have locked every subsequent test login out of
its own admin session for the rest of this pass, since this sandbox's
admin has no second factor enrolled.

**Roles had a real, confirmed bug**: `OrgRoles.tsx` rendered **two**
separate `<Modal><AddRole/></Modal>` instances — one wired to the header's
green "Create a Role" button, one to the black button below the roles
table — both bound to the exact same `createRoleModal` boolean state.
Opening either trigger flipped that shared state to `true` and mounted
*both* dialogs at once, stacked at the identical screen position
(confirmed live: both reported the exact same bounding box). Filling the
name field in what looked like the only visible form and reading the
value back showed it in a second, separate DOM element — the actual
symptom that surfaced this during testing. Fixed by keeping one canonical
`<Modal>` and turning the second trigger into a plain button that opens
the same shared instance rather than mounting its own copy. Verified live:
exactly one name input/description textarea now exists in the DOM, and
role creation still returns 200 and appears in the list. Added a permanent
regression test to `full-sweep.spec.ts`.

**Signups & Invite Codes had a third instance of the Redis-crash bug
class** — this one in `src/services/orgs/invites.py`, structurally
different from the assignments/usergroups/podcasts case fixed earlier:
invite codes are stored *entirely* in Redis (short-lived keys with a TTL,
no Postgres table at all), so there is no fallback data store to degrade
to the way there was for usage-tracking counters — this feature genuinely
requires a reachable Redis to function. The actual bug was narrower but
still real: `redis_conn_string` being configured (which it is, by
default) only proves a connection *string* exists, not that the Redis
server behind it is reachable — the real connection attempt happens
lazily inside `r.eval()`/`r.get()`/`r.delete()`, so a Redis that's down
surfaced as an unhandled `redis.exceptions.ConnectionError` deep in
library code: a raw 500 with a Python traceback as the response body,
which the browser reported as a misleading CORS failure (confirmed via
the backend log's full traceback — the same "Chrome mislabels any
response-less failure as CORS" pattern from the assignments bug).
Generating an invite code, listing them, fetching one, and deleting one
were all broken this way. Fixed with a `_get_redis_or_503()` wrapper that
pings eagerly and turns any Redis error into a clean `503 Service
Unavailable` with an actionable message ("Invite codes require a working
Redis connection, which is currently unavailable. Contact your
administrator.") — the frontend's existing generic error-toast plumbing
then surfaces that message directly to the admin instead of a blank
crash. Verified live: same 503 + clear toast, no more raw stack trace.
Added `test_create_invite_code_redis_down_gives_clean_503_not_raw_crash`
to `test_org_invites_service.py` (the existing suite's own
`_get_redis`-returns-`None` test only covered a theoretical case that
never happens in real code — `_get_redis` always returns a client object,
it just may not be able to reach anything — so it never caught this).
Updated that existing test's 4 assertions from 500 to 503 to match the
now-correct status code. 13/13 tests pass in that file; the broader
`-k invite` sweep across `src/tests/routers` is 35/35.

### Developers settings — API Access, Automations, Domains, SEO

Continued the sweep into the Developers tabs, actually filling in and
submitting each form rather than just confirming the pages load.

**API Access** (token creation) works correctly — creating a new API
token returns 200 and the token appears in the list immediately.

**Automations** (webhooks) works correctly once the right button was
identified: the page has two elements with overlapping-looking labels
("Add Endpoint" is the page-level trigger button, "Create Endpoint" is
the modal's actual submit button), which cost a few failed locator
guesses before checking real button text via
`page.locator('button').evaluateAll(...)`. Once pointed at the right
button, webhook creation returns 200 and the new endpoint appears in the
list.

**SEO** settings save and persist correctly across a reload.

**Domains** works correctly end-to-end for what can actually be tested in
this sandbox: submitting "Add Domain" with a fresh hostname returns a
clean 200 and opens a "Verify Domain" modal with real, distinct TXT
(`_learnhouse-verification.<host>`) and CNAME (`<host>` →
`default.learnhouse.io`) records to add at the domain's registrar, plus a
"Verify DNS" action. This is correctly gated on external DNS ownership
proof — the same bar used elsewhere in this pass for
environment-limited features (e.g. AI Playground generation): confirming
the creation call and verification-pending UI work cleanly, not that a
real domain can be fully verified from this sandbox. No bug found.

No permanent Playwright regression tests were added for these four —
unlike the Roles and invite-codes bugs, nothing here needed a fix, so
there was no specific regression to pin down; `full-sweep.spec.ts`'s
existing dashboard-route sweep already covers all four pages loading.

**Not yet covered by this pass**: submitting and grading an actual
assignment (only creation was exercised). Also not covered: whether the
same stale-while-revalidate
service worker causes an analogous "my own edit doesn't appear" problem on
any OTHER editor surface that hits
`/api/v1/courses|chapters|activities/...` without
`with_unpublished_activities=true` in the URL (the SEO tab, Access/roster
editing, contributor management, and drag-and-drop reordering all mutate
course-adjacent data through different endpoints/params) — worth a
follow-up sweep specifically hunting for that pattern elsewhere, now that
its signature (an edit that requires a hard reload to see) is known.

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

- ~~**SSO (real IdP integration — SAML/OIDC against an arbitrary school
  IdP)**~~ — **done, OIDC only, not SAML/WorkOS.** See `src/db/sso.py`'s
  module docstring for the full scope reasoning: a correct SAML 2.0
  implementation needs XML canonicalization and XML-signature verification
  done exactly right (XSW/wrapping-attack resistance in particular) — the
  kind of thing you use a vetted library for, not hand-roll, and this
  project has no SAML dependency. WorkOS (a third-party paid SSO-as-a-service
  product) is also not implemented — it would reintroduce an external paid
  dependency for a self-host project whose whole point is no vendor lock-in.
  Every provider actually supported — **Keycloak, Okta, Auth0, or any other
  IdP via a generic "custom_oidc" option** (this covers Google Workspace and
  Microsoft Entra ID/Azure AD too, both fully OIDC-compliant) — goes through
  one shared discovery + authorization-code-flow + PKCE path, since they all
  expose a standard `/.well-known/openid-configuration` document.
  DISCOVERY: this wasn't a build-from-nothing feature. The DB migration
  (`a1b2c3d4e5f6_add_sso_connection`), the full frontend client
  (`apps/web/services/auth/sso.ts` — config CRUD, check/authorize/callback,
  structured error codes, the login-page button) and even the session-
  provenance constant (`AUTH_METHOD_SSO`) already existed, clearly written
  against a backend contract that was never implemented — this pass built
  exactly that missing backend (`src/db/sso.py`, `src/services/auth/
  sso_oidc.py`, `src/routers/auth_sso.py`) to the existing contract, so
  **zero frontend changes were needed** — the login page's SSO button
  already calls `checkSSOEnabled`/`redirectToSSOLogin` correctly.
  Security: PKCE (S256) even though this is a confidential client (defense
  in depth against code interception); `state` is itself a short-lived
  signed JWT carrying the org/nonce/PKCE-verifier rather than a server-side
  session — works correctly whether or not Redis is configured, consistent
  with Redis being optional everywhere else in this project; ID tokens are
  verified by fetching the IdP's JWKS and checking signature + issuer +
  audience + nonce + expiry (not just decoded unchecked); the client secret
  is encrypted at rest with the same Fernet helper webhook signing secrets
  use; outbound calls to the IdP (discovery/token/JWKS) go through the same
  SSRF guard (`services/utils/ssrf_guard.py`) webhook delivery already uses.
  Auto-provisioning matches an existing org member by email first (no
  duplicate account), honors a per-connection `default_role_id`, and can be
  turned off per-org (`auto_provision_users=false`) to require accounts to
  already exist. A per-connection email-domain allowlist is supported.
  VERIFIED FOR REAL, not just by reading: with a live Postgres 16 database
  and a running backend (this sandbox turned out to have both, same as the
  rest of this session), exercised the full admin CRUD flow over real HTTP
  (create/read/update/delete a connection, provider catalog, `check`
  correctly flipping enabled/disabled) and the real DB-writing user
  provisioning logic (`_resolve_or_provision_user`/`_join_org`: new-user
  creation, idempotent re-resolution of the same email with no duplicate,
  matching an existing org member, `auto_provision_users=false` correctly
  blocking an unknown email) — all against the actual database, not mocks.
  Also verified real RS256 ID-token signature/nonce/audience/issuer/expiry
  checking against a genuine self-signed RSA keypair
  (`src/tests/services/test_sso_oidc_service.py`, 21 tests, all passing for
  real). **NOT verifiable in this sandbox**: the actual discovery/token-
  exchange HTTP calls to a real external IdP — this sandbox forces all
  outbound HTTPS through a local intercepting proxy for tooling reasons,
  which makes `assert_connected_peer_allowed`'s post-connect peer check
  (correctly) see the proxy's own address instead of the IdP's, and reject
  it — a sandbox artifact, not a code bug (the same guard is already
  proven-safe elsewhere in this codebase, e.g. webhook delivery). A real
  deployment without a forced outbound proxy needs a real Keycloak/Okta/
  Auth0/Google Workspace/Entra ID test to confirm the live discovery/token
  exchange end to end — the one piece this session's environment could not
  exercise for real.
- **Payments** — still not built, deliberately. Stripe billing exists in EE
  to let a SaaS operator sell course access to the public; a college
  self-hosting its own courses for its own students has no seller/buyer
  relationship for this to model. Revisit only if that changes.
- ~~**Advanced analytics**~~ / ~~**Audit logs (advanced tier)**~~ — **done,
  and a genuinely different situation from SSO/SCORM.** Investigating "what's
  actually missing" turned up that both were already FULLY BUILT, real,
  complete OSS code sitting right in this repo — not a withheld
  `apps/api/ee/` module at all: the per-student audit dossier
  (`routers/audit.py` — full RBAC, per-user dossier, multi-user summary
  rows, streaming CSV/JSON export with a formula-injection guard) and the
  advanced Tinybird analytics queries (`services/analytics/queries.py`'s
  `ADVANCED_QUERIES`: course dropoff, cohort retention, time-to-completion,
  peak usage hours, content-type effectiveness, new-vs-returning). Confirmed
  live: `curl`ing `/audit/user/{id}` in this session's OSS-mode deployment
  returned `403 analytics_advanced is not available in OSS mode` — a
  complete, working feature, blocked outright by a paywall check that has
  nothing to do with whether the code exists. Root cause: both routers'
  own plan-enforcement helpers called
  `_check_mode_bypass("analytics_advanced")`, which unconditionally 403s in
  OSS mode for anything in `EE_ONLY_FEATURES` — correct for a feature that
  really is withheld, wrong here since this feature isn't. Fixed by
  replacing that call, in exactly these two call sites
  (`routers/audit.py::_enforce_plan`, `routers/analytics.py`'s two
  `ADVANCED_QUERIES` gate blocks), with a direct
  `get_deployment_mode() == "saas"` check — SaaS-mode behavior (Pro/
  Enterprise plan required) is completely unchanged; OSS and EE modes now
  pass straight through, same precedent SCORM and SSO already established.
  Verified live against the real Postgres 16 DB in this session: the
  dossier, summary, and CSV export endpoints now return real data (a
  genuine login-history CSV came back with actual rows from this session's
  own test logins); the advanced-analytics dashboard endpoint now reaches
  its real 503 "Analytics not configured" (Tinybird isn't set up in this
  sandbox — the gate itself is confirmed bypassed, since that's a different
  failure mode than the 403 it returned before).
  **The one genuinely NEW thing built**: retention/purge, which really
  didn't exist anywhere before this. `user_audit_event` was, by its own
  docstring, "never updated or deleted" — correct for legal-record purposes
  but means unbounded growth with no privacy/storage escape hatch. Added a
  per-org retention policy (`OrganizationConfig.config["audit"]
  ["retention_days"]`, null = keep forever, the safe default; a 30-day
  floor guards against a fat-fingered short window silently nuking history)
  via `GET/PUT /audit/retention`, an on-demand `POST /audit/retention/purge`
  with a `dry_run` preview (always run this first — it's a bulk delete),
  a `cli.py audit-retention-run --dry-run` escape hatch, and a daily
  in-process scheduler (`services/audit/retention_scheduler.py`, same
  Redis-day-lock-as-optimization pattern as the weekly digest scheduler)
  gated by `LEARNHOUSE_AUDIT_RETENTION_ENABLED` (default off — matches the
  weekly-digest kill-switch precedent; the manual CLI/API purge always
  works regardless of the switch). SCOPE DECISION: purge only touches
  org-scoped rows (course/assignment/certificate events); login/logout
  events carry no `org_id` (a user authenticates once, not per-org), so
  which org's retention policy would apply to them is ambiguous — left out
  of automatic purge rather than guessed at. Verified for real: inserted a
  genuinely 40-day-old and a 20-day-old org-scoped row directly into the
  live Postgres DB, set a 30-day policy, confirmed dry-run counted exactly
  the 40-day-old row without deleting it, then confirmed a real purge
  deleted exactly that one row and left the 20-day-old row and all 7
  existing login/logout rows (`org_id IS NULL`) completely untouched.
  19 new tests (`test_audit_retention_service.py`) cover the pure config-
  parsing logic; the live-DB purge behavior above was hand-verified rather
  than scripted into a test, matching this session's established pattern
  for DB-writing paths.

SCORM, SSO, and now the audit/analytics gate fix are the EE-listed
capabilities (`EE_ONLY_FEATURES` in `deployment_mode.py` still lists
`'scorm'`, `'sso'`, and `'analytics_advanced'`, matching the constant's own
SaaS-plan-gating purpose — see below) that turned out to already be, or got
built as, real OSS code. Deliberately left `EE_ONLY_FEATURES` and
`plans.py` themselves untouched rather than editing shared SaaS-plan-gating
config — SaaS-mode behavior for every one of these features is completely
unchanged; only OSS/EE mode's specific call sites were fixed to stop
routing through a gate meant for something genuinely withheld. The
`'audit_logs'` key in that same set (distinct from `'analytics_advanced'`)
appears to be unused by any current router — nothing in this codebase gates
on it — so it may be either aspirational or superseded by the
`'analytics_advanced'` gate this pass actually found and fixed; left as-is
rather than guessing at intent for a key nothing reads.

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
- ~~At-risk student dashboard~~ — **done**, distinct from the existing
  per-course analytics (which is Tinybird-backed and TTL'd — a retention
  signal needs to still be true months later, so this is computed entirely
  from durable Postgres data: enrollment, grading, and completion, not the
  analytics event stream). A new "At-Risk" course-dashboard tab flags
  enrolled students on up to four independent signals: **inactive** (no
  login and no activity in this course for 14+ days), **failing** (2+
  GRADED submissions came back failed, via the exact `grade_display.passed`
  every other grading surface already computes), **missing_assignments**
  (2+ published assignments past this student's own EFFECTIVE due date —
  extensions honored via `get_effective_due_date` — with no submission row
  at all), and **low_progress** (enrolled 14+ days with under 25%
  completion). `risk_level` is "high" at 2+ signals, "medium" at exactly
  one; a student with zero signals is left out of the response entirely so
  the queue stays short enough to act on. SCOPE DECISION, disclosed in the
  service module's own docstring: this project has no course-schedule/
  syllabus model (no start/end dates, no weekly pacing plan), so "falling
  behind pace" is approximated as "enrolled a while ago but has completed
  very little" rather than compared against a real schedule — a real
  limitation, not an oversight. The day-math and flag-derivation logic
  (including the important "a student enrolled yesterday must not be
  flagged low_progress" edge case) were verified with a standalone script;
  the DB-aggregation half needs real-environment verification like
  everything else this session, since this sandbox has no live Postgres to
  run it against.
- ~~Verifiable digital credentials for certificates~~ — **done, Open Badges
  2.0, not a signed PDF.** A PDF would need a rendering dependency this
  project doesn't have (no reportlab/weasyprint/etc. anywhere in
  `pyproject.toml`), and would only ever prove authenticity to whoever
  bothers to check a signature by hand; an Open Badges 2.0 assertion is a
  real, portable, independently-verifiable credential a learner can hand to
  a recruiter, add to a Badgr backpack, or feed to any OB2-aware verifier
  — and needs nothing but JSON. Uses OB2's "hosted" verification method
  (no signing keys, no key-rotation story): three new public,
  unauthenticated endpoints under the existing `/certifications` router
  serve an Issuer Profile (`/openbadges/issuer/{org_uuid}.json`), a
  BadgeClass (`/openbadges/badgeclass/{certification_uuid}.json`), and an
  Assertion (`/openbadges/assertion/{user_certification_uuid}.json`) — the
  assertion's existence at that exact URL IS the verification proof.
  Everything is assembled live from EXISTING rows (`CertificateUser`,
  `Certifications`, `Course`, `Organization`) — no new table, the same
  "pure transformation of durable data" shape as the at-risk dashboard and
  gamification stats. A revoked certificate (`revoke_user_certificate`
  DELETES the `CertificateUser` row) 404s here identically to one that
  never existed, so there's no separate revocation flag to keep in sync —
  the existing verification page already relied on the same guarantee. The
  recipient's email is never exposed in the public assertion JSON: OB2's
  recommended privacy-preserving hashed-identity format is used, salted
  with a per-credential, app-secret-derived salt (stable across requests,
  not guessable without the secret) — verified deterministic, per-
  credential-unique, and non-leaking with a standalone script. The
  existing certificate verification page gained an "Open Badges 2.0" card
  linking to the assertion JSON. KNOWN LIMITATIONS: (1) the BadgeClass
  `image` field falls back course thumbnail → org logo → omitted entirely
  if neither exists, rather than baking a placeholder image — most OB2
  verifiers tolerate a missing image despite the spec listing it as
  required; (2) the Issuer endpoint's plan-gate dependency
  (`require_plan_for_certifications`, shared with the rest of the
  certificates feature) doesn't recognize an `org_uuid` path param, so in
  SaaS mode that one endpoint's plan check silently no-ops rather than
  enforcing — a pre-existing "soft ceiling, not the last line of defence"
  fallback in that shared dependency, not something this feature
  introduced, and irrelevant in OSS/self-hosted mode where the same
  dependency always bypasses anyway. Needs real-environment verification
  like everything else this session, especially feeding a real assertion
  URL to an actual OB2 verifier (Badgr) rather than just checking the JSON
  shape by eye.
- ~~Weekly digest email~~ — **done**, a deliberately much smaller sibling of
  the existing org-admin lifecycle nudges (`services/nudges/`) rather than
  an extension of them: one email type, one weekly cadence, no catalog/
  spec system, no per-track pacing. Runs on its own in-process weekly
  scheduler (`services/digest/scheduler.py`, mirroring the nudge
  scheduler's daily-tick pattern — Redis day-lock as an optimisation,
  the send ledger's unique dedupe key as the actual correctness
  guarantee) — **not SaaS-gated**, unlike nudges: a self-hosted college is
  exactly this feature's intended audience, so the only gate is the
  `LEARNHOUSE_WEEKLY_DIGEST_ENABLED` kill switch (default off) plus each
  student's own opt-out. That opt-out is a NEW, independent
  `EmailPreference.weekly_digest_opt_out` field — deliberately not reusing
  `lifecycle_opt_out`, since an org admin who is also a student elsewhere
  should be able to opt out of one without the other. For every
  (student, org) enrollment with at least one signal, the email lists
  "due this week" (published assignments whose effective due date —
  extensions honored — falls in the next 7 days, not yet submitted) and
  "you haven't started" (other unsubmitted published assignments), each
  capped at 5 items; a student with nothing to show gets no email at all.
  An operator dry-run is available via `python cli.py digest-run
  --dry-run` (mirrors `nudges-run`). SCOPE DECISIONS, disclosed in the
  service module's own docstring: (1) "haven't started" lists only
  unsubmitted ASSIGNMENTS, never ordinary reading/content activities — a
  content page has no deadline pressure, and listing every unread page
  would make the email noisy rather than useful; (2) an assignment already
  past its own effective due date is excluded from both sections — that's
  the at-risk dashboard's job, not this email's, and repeating "this is
  late" every Monday would read as a nag; (3) only English copy was
  written (`services/email/digest_translations.py`) — every other locale
  already falls back to English via the existing `t()` translation
  helper's design, same disclosed limitation as this session's other
  new UI copy. No frontend preference toggle was added — matches the
  existing lifecycle-nudge precedent exactly (unsubscribe-link-only, no
  account-settings UI for either category). The date-bucketing and
  weekly dedupe-key logic were verified with standalone scripts; the
  scheduler's day-of-week/hour math was verified the same way. Needs
  real-environment verification like everything else this session,
  especially a real Resend send and a real weekly tick across a
  server restart.
- ~~Gamification (points, streaks, badges)~~ — **done, deliberately
  private.** Directly addresses the "weigh carefully for a college
  audience" caution above by never becoming a public leaderboard: a new
  "Achievements" account tab shows a student ONLY their own points,
  current streak, and badges in one org — nothing ranks or compares
  students, nothing is pushed via email/notification, and there is no
  endpoint that lists another student's stats. Like the at-risk dashboard
  and unlike the certificates feature, this is a LIVE aggregation over
  existing durable data (the `user_audit_event` log plus discussions/
  comments) — no new table, no stored point ledger. Points: 5 for
  completing an activity, 5 for submitting an assignment (+10 bonus if it
  was graded and passed), 100 for finishing a course, 50 for a
  certificate, 10 per discussion post, 3 per comment. Streak: consecutive
  calendar days with real coursework activity in that org (login alone
  doesn't count — opening the app isn't participation), with a one-day
  grace so the count doesn't reset to zero the instant midnight passes
  before the student opens the app. Badges are a small code-defined
  catalog (first activity, 7/30-day streaks, first discussion, 10
  comments, 1st/3rd certificate, 100/500 points) — not admin-configurable,
  the same way the nudge catalog is code rather than a table. The
  streak-math (grace period, broken-streak, longest-vs-current) and the
  badge-threshold logic were both verified with standalone scripts against
  hand-built fixtures. Needs real-environment verification like everything
  else this session, especially that the points/streak actually feel right
  once real student activity accumulates rather than just being
  arithmetically correct.

**Access / scale**
- ~~Offline-capable course content~~ — **done, narrowly scoped: data
  caching, not a full offline app shell.** A hand-rolled service worker
  (`public/sw.js` — no next-pwa/Workbox dependency added) caches, via an
  ALLOWLIST of path patterns (`/api/v1/courses/`, `/api/v1/chapters/`,
  `/api/v1/activities/` — never auth/users/payments/anything else), the
  GET responses for course meta, chapter, and activity content using
  stale-while-revalidate, plus Next.js's content-hashed static assets
  (`/_next/static/*`) cache-first. Only GET requests are ever touched —
  no offline write support (quiz answers, submissions) is attempted; that
  is a background-sync problem this does not solve. A `manifest.json`
  makes the app installable as a bonus. KNOWN LIMITATIONS, disclosed in
  `sw.js`'s own docstring: (1) this caches content the student has
  ALREADY opened in the current tab — it does not precache a whole
  course, so it will not spare data by prefetching everything before a
  trip; (2) a COLD full-page reload with zero connectivity is not
  supported (no offline-fallback document caching) — that would need a
  real Workbox/next-pwa build-time integration, a materially bigger
  change than a runtime script can safely replicate by hand; reopening a
  tab that was already loaded once while online, or navigating within an
  already-open tab, both work offline for previously-viewed content.
  PRIVACY LIMITATION, also disclosed there: the Cache API has no notion of
  "which account" fetched a response, exactly like ordinary browser disk
  cache — on a SHARED device, a second account logged into the same
  browser profile could otherwise read the first account's cached
  restricted content while offline. Mitigated, not eliminated: the app now
  clears every service-worker cache on sign-out
  (`services/offline/clearOfflineCache.ts`), wired into all three
  logout paths (`AuthContext`'s `handleSignOut`, its standalone `signOut`
  export, and the cross-tab `LOGOUT` broadcast handler) — this protects
  anyone who actually signs out, not someone who just closes the tab.
  The service-worker's own URL-pattern matching (which requests are
  eligible for caching, and that mutating methods are never touched
  regardless of path) was verified with a standalone script. Needs
  real-environment verification like everything else this session,
  especially registering successfully across real browsers and surviving
  an actual campus-wifi dropout mid-session.
- ~~Live video conferencing / virtual classroom~~ — **done, embedded
  meeting link only, not native WebRTC.** A native in-app video call would
  need a real-time media server, NAT traversal (TURN/STUN), and
  room/participant management — categorically larger than a hand-rolled
  feature in one pass, and this codebase has none of that infrastructure
  today. Instead, a new "Live Sessions" course-dashboard tab lets an
  instructor schedule a session with any http(s) meeting link (Zoom,
  Google Meet, Teams, ...), a title/description, and a start/optional-end
  time; the actual call happens entirely on the third-party platform the
  link points at. Students see the schedule with a "Join" button directly
  on the course page, AND the sessions now appear on the existing ICS
  calendar feed (`services/users/calendar_feed.py`, built earlier this
  session for assignment due dates) as VEVENTs carrying the meeting link
  in the standard ICS `URL` property, so most calendar clients render it
  as a clickable join link right on the event — a genuine free tie-in
  between the two features. The meeting URL is server-side validated to
  be a plain `http(s)` link before it's ever stored (rejects
  `javascript:`/`data:`/other schemes) — since it's rendered as an
  unescaped clickable href, an unvalidated value would otherwise be an
  XSS vector for whoever clicks Join; verified against both legitimate
  meeting links and a battery of malicious schemes with a standalone
  script. KNOWN LIMITATIONS: (1) no recurring sessions — each one is a
  single scheduled occurrence, a weekly standing class needs one row per
  week; (2) no reminder notifications (no email/push before a session
  starts) — the calendar feed is the only advance-notice mechanism;
  (3) same floating-time (no per-org timezone) limitation the ICS feed
  already disclosed for assignment due dates applies here identically.
  Needs real-environment verification like everything else this session.
- ~~Learning path / prerequisite enforcement~~ — **done, at both the
  course and the chapter level.** A course can require another course in
  the SAME org to be fully completed before a learner may self-enroll
  (`Course.prerequisite_course_id`, enforced at `add_course_to_trail` —
  the self-enrollment endpoint); a chapter can require another chapter in
  the SAME course to be fully completed before it unlocks
  (`Chapter.prerequisite_chapter_id`, enforced in the existing
  per-request lock computation both the course-TOC read and the
  single-activity read already run). "Fully completed" reuses the exact
  definition every other completion-gated feature in this app already
  relies on (`is_course_fully_completed` for courses;
  a new `is_chapter_fully_completed` — same COUNT-aggregate shape, just
  scoped to a chapter instead of a whole course — for chapters), so a
  learner's certificate-eligibility, at-risk "low progress" signal, and
  prerequisite status can never quietly disagree about what "completed"
  means. The prerequisite gate is deliberately INDEPENDENT of the existing
  usergroup-restriction lock: a usergroup grant unlocks RESTRICTED content
  for someone who's allowed to see it, but never bypasses the prerequisite
  sequencing — verified with a standalone script covering every
  restriction/prerequisite/usergroup-grant combination, including the
  cases that must NOT unlock (restricted-and-unmet, granted-but-unmet).
  `ChapterRead`/`ActivityRead` gained a `lock_reason` field
  ("restricted" | "prerequisite" | null) alongside the pre-existing
  `is_locked` boolean, so the frontend can render "join a group" vs
  "finish chapter X first" instead of one generic locked state. Both
  levels get dedicated set/clear endpoints
  (`PUT /courses/{uuid}/prerequisite`, `PUT /chapters/{id}/prerequisite`)
  rather than folding into the generic course/chapter update endpoints,
  since those update loops only ever SET a non-None field and can never
  clear one — a prerequisite genuinely needs to be un-settable. Bulk
  roster import (instructor-driven enrollment) deliberately bypasses the
  course-level prerequisite — that's an explicit override, not a
  loophole. KNOWN LIMITATIONS: (1) no cycle detection across a chain of
  prerequisites (course A requires B requires A) — the self-reference
  case (a course/chapter requiring itself) IS rejected, but a longer
  cycle through several courses/chapters is not caught, and would simply
  make every course in the cycle permanently unenrollable; (2) no
  UI badge on the course card itself showing "locked, complete X first"
  before a learner tries to enroll — the requirement is only surfaced (a)
  informationally in the instructor's own prerequisite-setting dropdown
  and (b) as a clear 403 message at the moment of the enroll attempt,
  to avoid adding per-viewer completion computation to the course-metadata
  endpoint's existing anonymous-response cache path. Needs
  real-environment verification like everything else this session.
- **Native mobile app wrapper (iOS/Android) — explicitly NOT attempted,
  and not just deprioritized.** Every other item in this file is a code
  change to the repo already checked out in this session; this one isn't
  one at all. A native app is a SEPARATE codebase (Swift/Kotlin, or a
  React Native/Capacitor project with its own build toolchain), plus an
  App Store / Play Store developer account, signing certificates, and a
  review/release pipeline — none of which exist here, none of which a
  coding session against this web repo can create, and the offline-PWA
  work earlier in this section (a real service worker + installable
  manifest) already covers a meaningful slice of what a "wrapper" would
  have bought without any of that. The doc's own original framing —
  "only worth it once the web app's mobile experience is confirmed
  insufficient on its own" — still holds and is the right bar before
  anyone starts a real native project, not a coding-session task.

## Small cleanup items

- [x] ~~`seb-integration-discussion.md` at the repo root is a leftover draft
      from an earlier (now abandoned) plan to post this work as an upstream
      Discussion — irrelevant to the self-host deployment now, safe to delete.~~
      Done — deleted. Confirmed stale: it proposed `require_safe_exam_browser`/
      `seb_config_key`/`seb_quit_password` fields as a future plan, but the real
      SEB integration (those same fields on `Assignment`, header-hash
      verification, downloadable `.seb` config) was already built and merged
      earlier in this project, with its own `test_seb_service.py` coverage.
- [x] ~~No `pytest` test file exists for the SCORM manifest parser/service yet
      (SEB got `test_seb_service.py`; SCORM only has the throwaway sanity
      scripts used during development, never committed as real tests).~~
      Done — added `apps/api/src/tests/services/test_oss_scorm_service.py`
      (28 tests). Worth noting why this wasn't already covered: every existing
      `test_scorm_*.py` file in the suite (`test_scorm_parsing.py`,
      `test_scorm_content_path.py`, `test_scorm_extract.py`, etc.) targets
      `ee/services/scorm/scorm.py` via `pytest.importorskip` — the Enterprise
      Edition SCORM module, which this OSS repo doesn't ship, so all 8 of
      those files skip cleanly and exercise nothing here. The actual OSS
      SCORM implementation (`src/services/courses/activities/scorm.py`,
      SCORM 1.2 only) had no test file importing it directly. The new file
      imports that module with no `importorskip`, reusing the existing
      `src/tests/fixtures/scorm_packages.py` manifest builders (they're
      generic SCORM-spec XML, not EE-specific), and covers: `validate_scorm_zip`,
      `sanitize_path`, `detect_scorm_version` (1.2 vs 2004, single/multi-SCO),
      `extract_scos_from_manifest` (nested items, xml:base, mastery score,
      Rise/Windows-path normalization, missing-href-uses-first-file), 
      `get_package_title`, and `_safe_extract_zip`'s security guards (path
      traversal, symlink entries, per-file/aggregate size caps, entry-count
      cap) plus an XXE check on `defusedxml`. Not covered: the FastAPI-route
      functions (`upload_scorm_package`, `serve_scorm_file`,
      `get_scorm_tracking`, etc.) since those need a running app + DB to
      exercise meaningfully — only the pure/file-system-local functions are
      tested here, matching the existing test files' own scope. Actually
      installed the full pinned dependency set (`fastapi`, `sqlmodel`,
      `defusedxml`, `pytest`, etc. via pip) and ran the file for real with
      `python3 -m pytest` — all 28 tests pass against the live module; this
      is executed coverage, not just design-verified.
