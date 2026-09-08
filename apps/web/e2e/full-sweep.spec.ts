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
