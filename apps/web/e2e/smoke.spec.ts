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

    // Bare path, no /orgs/{slug} prefix: proxy.ts's tenant-scoped rewrite
    // (section 11) unconditionally prepends /orgs/{slug} to every incoming
    // pathname with no guard against a path that already has it — navigating
    // straight to /orgs/default/dash/... double-prefixes into
    // /orgs/default/orgs/default/dash/... and 404s. Every dashboard link in
    // the app itself already navigates with bare paths; only a test/manual
    // URL would get this wrong.
    const resp = await page.goto('/dash/courses')
    expect(resp?.status()).toBe(200)
    // The dashboard shell (sidebar/nav) rendering at all — not a blank
    // error page — is the bar here; there's no seeded course content yet.
    await expect(page.locator('body')).not.toContainText('Application error')
    await expect(page.locator('body')).not.toContainText('500')
  })

  test('SSO admin settings page reflects the real backend, not a paywall card', async ({ page }) => {
    // Regression test for a chain of bugs found and fixed in this session:
    // an EE-feature paywall gate (FeatureGate -> useResolvedFeature ->
    // resolve_feature() backend + planMeetsRequirement's OSS-mode hardcoded
    // "never meets an enterprise requirement" rule) was hiding this fully
    // built, working OSS feature behind an "Upgrade to Enterprise" card. See
    // PENDING_FEATURES.md for the full chain (5 independent layers, each
    // needing its own fix).
    await page.goto('/login')
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15_000,
    })

    const resp = await page.goto('/dash/developers/sso')
    expect(resp?.status()).toBe(200)

    // Dismiss the first-run onboarding modal if it's covering the page.
    await page.getByText('Get Started', { exact: false }).click({ timeout: 5_000 }).catch(() => {})
    await page.getByText("Let's go", { exact: false }).click({ timeout: 3_000 }).catch(() => {})

    // The paywall card's own text — must be absent now that sso resolves as
    // enabled in OSS mode.
    await expect(page.locator('body')).not.toContainText('Upgrade to')
    // The real settings form: a live GET /auth/sso/providers round trip
    // populated the provider dropdown, defaulted to the first real provider.
    await expect(page.getByLabel(/sso provider/i).or(page.getByText('SSO Provider'))).toBeVisible()
    await expect(page.getByText('Issuer URL', { exact: false }).first()).toBeVisible()
  })

  test('SCORM import panel is usable, not gated, in OSS mode', async ({ page }) => {
    // Regression test for the same EE-feature-gate chain as the SSO test above,
    // plus a distinct bug found only by clicking through this specific surface:
    // ImportTypeSelector.tsx rendered a <PlanBadge requiredPlan="enterprise" />
    // unconditionally next to the SCORM import option. PlanBadge decides
    // whether to show via planMeetsRequirement(), whose 'oss' branch hardcodes
    // false for any 'enterprise' requirement — so even though the import
    // button itself was correctly enabled (it reads resolved_features.scorm
    // directly), the badge still told admins the feature was locked. Fixed by
    // only rendering the badge when the resolved feature says it's actually
    // unavailable, instead of re-deriving that from the plan tier.
    await page.goto('/login')
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15_000,
    })

    const resp = await page.goto('/dash/courses')
    expect(resp?.status()).toBe(200)
    await page.getByText('Get Started', { exact: false }).click({ timeout: 5_000 }).catch(() => {})
    await page.getByText("Let's go", { exact: false }).click({ timeout: 3_000 }).catch(() => {})

    await page.getByText('Import Course', { exact: false }).click({ timeout: 10_000 })

    const scormButton = page.getByText('SCORM Package').locator('xpath=ancestor::button')
    await expect(scormButton).toBeEnabled()
    await expect(scormButton).not.toContainText('Enterprise')

    await scormButton.click()
    await expect(page.getByText('Import SCORM', { exact: false })).toBeVisible()
    await expect(page.getByText('Click to upload or drag and drop', { exact: false })).toBeVisible()
  })
})
