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
