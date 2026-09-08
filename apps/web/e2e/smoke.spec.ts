import { test, expect } from '@playwright/test'

/**
 * Golden-path smoke suite against a real, running stack (Postgres +
 * FastAPI backend + Next.js frontend, no mocks). Credentials come from
 * the env vars the backend install step (`cli.py install --short`) was
 * seeded with — see PENDING_FEATURES.md for exact setup steps.
 *
 * Scope: unauthenticated homepage, the password-login round trip against
 * the real backend, and that an authenticated session reaches the
 * dashboard and can view the (empty) course list without erroring. This
 * is a smoke suite, not full feature coverage — see PENDING_FEATURES.md
 * for what a fuller E2E pass would still need to add (course creation,
 * assignment submission, SCORM playback, etc.), all of which need seed
 * content this run doesn't create.
 */

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@school.dev'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe123!'

test.describe('Golden path', () => {
  test('homepage loads and offers a login link', async ({ page }) => {
    const response = await page.goto('/')
    expect(response?.ok()).toBeTruthy()
    await expect(page).toHaveTitle(/LearnHouse|Default Organization/i)
  })

  test('login page renders the password form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('admin can log in with password and reach the dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
    await page.locator('button[type="submit"]').click()

    // A successful login redirects off /login — either to /home or
    // straight into an org context, depending on how many orgs this user
    // belongs to. Either way, staying on /login means the login failed.
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15_000,
    })
    expect(page.url()).not.toContain('/login')
  })

  test('authenticated session can open the org dashboard without erroring', async ({ page }) => {
    await page.goto('/login')
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15_000,
    })

    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await page.goto('/orgs/default/dash/courses')
    // The dashboard shell (sidebar/nav) rendering at all — not a blank
    // error page — is the bar here; there's no seeded course content yet.
    await expect(page.locator('body')).not.toContainText('Application error')
    await expect(page.locator('body')).not.toContainText('500')
  })
})

// NOT added: a test for the SSO admin settings page
// (/orgs/{slug}/dash/developers/sso). Attempting to verify it live surfaced
// a real, pre-existing, unrelated bug — see PENDING_FEATURES.md's "Small
// cleanup items" — every [subpage]-style dashboard settings route 404s
// (confirmed for /dash/developers/api, /dash/org/settings/general, and
// /dash/developers/sso alike, with a fresh dev server and no .next cache),
// not something introduced by this session's SSO/audit/analytics work. The
// backend and the OSS_BLOCKED_FEATURES frontend fix are independently
// verified (real HTTP calls in PENDING_FEATURES.md); a browser-level test
// of the settings PAGE itself has to wait until that separate bug is fixed.
