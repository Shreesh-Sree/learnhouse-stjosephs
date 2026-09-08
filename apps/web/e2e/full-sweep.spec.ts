import { test, expect, Page } from '@playwright/test'

/**
 * Broad end-to-end sweep across every top-level dashboard feature area,
 * run once against a real Postgres + FastAPI backend + Next.js frontend
 * (no mocks). This is NOT exhaustive per-feature coverage — it is a
 * golden-path health check (does the page load clean, does the primary
 * "create X" action work) for every area reachable from the dashboard
 * sidebar, run on user request after the earlier SSO/SCORM/analytics gate
 * fixes to catch anything else broken end to end.
 *
 * Scope note: deep feature-specific behavior (grading rubrics, SCORM
 * playback fidelity, SEB enforcement, etc.) stays out of scope here — see
 * PENDING_FEATURES.md for what's already covered by targeted suites
 * elsewhere (pytest, bun test, smoke.spec.ts).
 */

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@school.dev'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe123!'

async function login(page: Page) {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15_000 })
}

async function dismissOnboarding(page: Page) {
  await page.getByText('Get Started', { exact: false }).click({ timeout: 3_000 }).catch(() => {})
  await page.getByText("Let's go", { exact: false }).click({ timeout: 2_000 }).catch(() => {})
}

async function assertPageHealthy(page: Page, path: string) {
  const resp = await page.goto(path)
  expect(resp?.status(), `${path} should return 200`).toBe(200)
  await dismissOnboarding(page)
  const body = page.locator('body')
  await expect(body, `${path} should not show an application error`).not.toContainText('Application error')
  await expect(body, `${path} should not show a server error`).not.toContainText('500: Internal Server Error')
  await expect(body, `${path} should not show a client-side exception`).not.toContainText('client-side exception')
}

test.describe.configure({ mode: 'serial' })

test.describe('Dashboard sweep — every top-level area loads clean', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  const routes: [string, string][] = [
    ['Home', '/dash'],
    ['Courses', '/dash/courses'],
    ['Assignments', '/dash/assignments'],
    ['Library', '/dash/library'],
    ['Communities', '/dash/communities'],
    ['Podcasts', '/dash/podcasts'],
    ['Boards', '/dash/boards'],
    ['Playgrounds', '/dash/playgrounds'],
    ['Analytics', '/dash/analytics'],
    ['Users', '/dash/users/settings/users'],
    ['UserGroups', '/dash/users/settings/usergroups'],
    ['Roles', '/dash/users/settings/roles'],
    ['Signups', '/dash/users/settings/signups'],
    ['Add member', '/dash/users/settings/add'],
    ['Sign-in', '/dash/users/settings/sign-in'],
    ['Two-factor', '/dash/users/settings/two-factor'],
    ['Audit logs', '/dash/users/settings/audit-logs'],
    ['Org general', '/dash/org/settings/general'],
    ['Org branding', '/dash/org/settings/branding'],
    ['Org menu', '/dash/org/settings/menu'],
    ['Org landing', '/dash/org/settings/landing'],
    ['Org usage', '/dash/org/settings/usage'],
    ['Org other', '/dash/org/settings/other'],
    ['Org danger zone', '/dash/org/settings/danger'],
    ['Developers API', '/dash/developers/api'],
    ['Developers automations', '/dash/developers/automations'],
    ['Developers domains', '/dash/developers/domains'],
    ['Developers SEO', '/dash/developers/seo'],
    ['Developers SSO', '/dash/developers/sso'],
  ]

  for (const [label, path] of routes) {
    test(`${label} (${path}) loads without erroring`, async ({ page }) => {
      await assertPageHealthy(page, path)
    })
  }
})

test.describe('Course editor — chapters/activities appear without a reload', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('creating a chapter and an activity updates the editor live', async ({ page }) => {
    // Regression test for a real, severe bug found in this session: public/sw.js
    // (an offline-reading service worker built earlier, deliberately caching GET
    // /api/v1/courses|chapters|activities/... with a stale-while-revalidate
    // strategy so a student's already-opened lesson keeps working offline) was
    // ALSO intercepting the dashboard course editor's own requests — including
    // ones carrying with_unpublished_activities=true, which only the editor ever
    // sends. That meant a teacher who created a chapter or activity would not
    // see it appear without a full page reload: every GET immediately after a
    // write served the stale pre-write cache entry, one request behind, no
    // matter what triggered the refetch (react-query invalidation, an explicit
    // manual fetch — all equally intercepted). `cache: 'no-store'` on the fetch
    // call never helped, because SW interception happens before the browser's
    // own HTTP cache semantics are even consulted.
    //
    // Fixed at the true source: sw.js now recognizes with_unpublished_activities
    // =true as an editor request and always goes straight to the network for
    // it, leaving the offline-reading cache path (used only by published-content
    // readers, who never send that flag) untouched. Also hardened the mutation
    // call sites themselves (NewActivityButton, EditCourseStructure,
    // ChapterElement, ActivityElement, AssignmentActivityModal) to push a
    // directly-fetched fresh course-meta response into the query cache via
    // setQueryData rather than invalidateQueries + hope, which is more robust
    // regardless of caching layer.
    await page.goto('/dash/courses')
    await dismissOnboarding(page)

    // Create a throwaway course to edit, rather than depending on seeded data.
    await page.getByText('New Course', { exact: false }).click({ timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.getByText('Start from Scratch', { exact: false }).click({ timeout: 5_000 })
    await page.waitForTimeout(500)
    const courseName = 'E2E_STRUCTURE_TEST_' + Date.now()
    const createCourseDialog = page.getByRole('dialog')
    await createCourseDialog.locator('input').first().fill(courseName)
    await createCourseDialog.locator('textarea').first().fill('Course created by the full-sweep E2E course-editor regression test.')
    await page.getByRole('button', { name: /create course/i }).click({ timeout: 5_000 })
    await page.waitForURL((url) => url.pathname.includes('/dash/courses/course/'), { timeout: 15_000 })

    // Land on the content/structure tab. Course creation auto-redirects here
    // with ?new_activity=1, which auto-opens the Create Activity modal for the
    // first chapter — close it, we'll drive activity creation explicitly below.
    await page.goto(page.url().replace(/\/[a-z]+$/, '/content'))
    await dismissOnboarding(page)
    await page.waitForTimeout(1000)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)

    const chapterName = 'CHAPTER_' + Date.now()
    await page.getByText('Add Chapter', { exact: false }).click({ timeout: 10_000 })
    await page.waitForTimeout(500)
    const newChapterDialog = page.getByRole('dialog')
    await newChapterDialog.locator('input').first().fill(chapterName)
    await newChapterDialog.locator('textarea').first().fill('A chapter created by an E2E test.')
    await page.getByRole('button', { name: 'Create Chapter' }).click({ timeout: 5_000 })
    // The critical assertion: visible WITHOUT any page.reload() or page.goto().
    await expect(page.getByText(chapterName, { exact: false }).last()).toBeVisible({ timeout: 15_000 })

    const activityName = 'ACTIVITY_' + Date.now()
    await page.getByText('Add Activity', { exact: false }).last().click({ timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.getByText('Dynamic Page', { exact: false }).click({ timeout: 5_000 })
    await page.waitForTimeout(500)
    await page.locator('input[placeholder="Enter a name..."]').fill(activityName)
    await page.getByRole('button', { name: 'Create activity' }).click({ timeout: 5_000 })
    await expect(page.getByText(activityName, { exact: false })).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('Assignment and usergroup creation — real Redis-crash regression', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('creating an assignment succeeds (was a guaranteed 500 without Redis)', async ({ page }) => {
    // Regression test for a severe bug: increase_feature_usage() in
    // security/features_utils/usage.py called _get_redis_client() with no
    // guard for the "assignments"/"usergroups"/"podcasts" features — that
    // function deliberately raises HTTP 500 when Redis is unreachable, so
    // every assignment/usergroup/podcast create or delete 500'd outright in
    // any Redis-less deployment (this project treats Redis as optional
    // everywhere else). Fixed to skip Redis tracking outside SaaS mode
    // (where the usage counter is a no-op anyway) and fail open even in
    // SaaS mode. The chapter-picker bug this test also exercises
    // (NewActivityModal's Assignments step needs a real chapter to place
    // the assignment in) was a separate fix: getCourse() → getCourseMetadata().
    await page.goto('/dash/courses')
    await dismissOnboarding(page)
    await page.getByText('New Course', { exact: false }).click({ timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.getByText('Start from Scratch', { exact: false }).click({ timeout: 5_000 })
    await page.waitForTimeout(500)
    const createCourseDialog = page.getByRole('dialog')
    await createCourseDialog.locator('input').first().fill('E2E_ASSIGN_COURSE_' + Date.now())
    await createCourseDialog.locator('textarea').first().fill('Course for the assignment-creation regression test.')
    await page.getByRole('button', { name: /create course/i }).click({ timeout: 5_000 })
    await page.waitForURL((url) => url.pathname.includes('/dash/courses/course/'), { timeout: 15_000 })

    await page.goto(page.url().replace(/\/[a-z]+$/, '/content'))
    await dismissOnboarding(page)
    await page.waitForTimeout(1000)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)

    const assignmentName = 'REGRESSION_ASSIGN_' + Date.now()
    await page.getByText('Add Activity', { exact: false }).first().click({ timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.getByText('Assignments', { exact: false }).last().click({ timeout: 5_000 })
    await page.waitForTimeout(800)
    const assignDialog = page.getByRole('dialog')
    await assignDialog.locator('input').first().fill(assignmentName)
    await assignDialog.locator('textarea').first().fill('Created by the assignment-creation regression test.')
    await page.waitForTimeout(300)

    const submitBtn = assignDialog.getByRole('button', { name: 'Create activity' })
    await submitBtn.scrollIntoViewIfNeeded()
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/assignments/') && r.request().method() === 'POST', { timeout: 15000 }),
      submitBtn.click({ timeout: 10_000 }),
    ])
    expect(resp.status(), 'assignment creation must not 500').toBeLessThan(400)
    await expect(page.getByText(assignmentName, { exact: false })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 5_000 })
  })

  test('creating a usergroup succeeds (was a guaranteed 500 without Redis)', async ({ page }) => {
    await page.goto('/dash/users/settings/usergroups')
    await dismissOnboarding(page)
    const groupName = 'E2E_GROUP_' + Date.now()
    await page.getByRole('button', { name: 'Create a UserGroup' }).click({ timeout: 10_000 })
    await page.waitForTimeout(800)
    const dialog = page.getByRole('dialog')
    await dialog.locator('input').first().fill(groupName)

    const submitBtn = dialog.getByRole('button', { name: /create/i })
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/usergroups') && r.request().method() === 'POST', { timeout: 15000 }),
      submitBtn.click({ timeout: 10_000 }),
    ])
    expect(resp.status(), 'usergroup creation must not 500').toBeLessThan(400)
    await expect(page.getByText(groupName, { exact: false })).toBeVisible({ timeout: 15_000 })
  })
})

test.describe('Org general settings — save works without an unrelated required field', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('saving footer text does not require picking an Organization Label', async ({ page }) => {
    // Regression test: OrgEditGeneral.tsx's Yup schema required `label` (a
    // discovery/category taxonomy field — "Business", "Gaming", "Tech", etc.
    // — Optional[str] on the backend) for the ENTIRE general-settings form,
    // blocking every save, including completely unrelated fields like footer
    // text, unless a label had been picked first. The seeded default org
    // ships with no label set, so this was a first-save wall for literally
    // every fresh self-host install. Fixed by making the frontend schema
    // match the backend's own optional contract.
    await page.goto('/dash/org/settings/general')
    await dismissOnboarding(page)

    const footerText = 'E2E_FOOTER_' + Date.now()
    await page.locator('input[placeholder="Enter footer text..."]').fill(footerText)
    await page.getByRole('button', { name: 'Save Changes' }).click({ timeout: 10_000 })
    await expect(page.getByText('Organization label is required', { exact: false })).toHaveCount(0, { timeout: 5_000 })

    await page.waitForTimeout(1500)
    await page.reload()
    await dismissOnboarding(page)
    await expect(page.locator('input[placeholder="Enter footer text..."]')).toHaveValue(footerText, { timeout: 15_000 })
  })
})

test.describe('Roles — Create a Role does not render twice', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('opening the create-role modal from either trigger mounts exactly one form', async ({ page }) => {
    // Regression test: OrgRoles.tsx rendered TWO separate <Modal><AddRole/></Modal>
    // instances — one wired to the header's green "Create a Role" button, one to
    // the black button below the roles table — both bound to the SAME
    // createRoleModal boolean state. Opening either one flipped that shared
    // state to true, mounting BOTH dialogs at once, stacked at the exact same
    // screen position (identical bounding boxes, confirmed live) — filling the
    // "first" name input and reading it back showed the value in a second,
    // separate element. Fixed by keeping one canonical <Modal> and making the
    // second trigger a plain button that opens the same shared instance.
    await page.goto('/dash/users/settings/roles')
    await dismissOnboarding(page)
    await page.getByRole('button', { name: 'Create a Role' }).first().click({ timeout: 10_000 })
    await page.waitForTimeout(800)

    await expect(page.locator('input[placeholder="e.g., Course Manager"]')).toHaveCount(1)
    await expect(page.locator('textarea[placeholder="Describe what this role can do..."]')).toHaveCount(1)

    const roleName = 'E2E_ROLE_' + Date.now()
    await page.locator('input[placeholder="e.g., Course Manager"]').fill(roleName)
    await page.locator('textarea[placeholder="Describe what this role can do..."]').fill('Regression test role.')
    await page.locator('label:has-text("Read")').first().click({ timeout: 5_000 })

    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/roles') && r.request().method() === 'POST', { timeout: 15000 }),
      page.getByRole('button', { name: 'Create Role', exact: true }).click({ timeout: 10_000 }),
    ])
    expect(resp.status(), 'role creation must succeed').toBeLessThan(400)
    await expect(page.getByText('Created new role', { exact: false })).toBeVisible({ timeout: 10_000 })
  })
})
