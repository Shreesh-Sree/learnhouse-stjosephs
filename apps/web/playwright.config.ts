import { defineConfig, devices } from '@playwright/test'

/**
 * Runs against a stack the caller starts and seeds itself (real Postgres +
 * uvicorn backend + `next dev`/`next start` frontend) — no webServer entry
 * here, since spinning up Postgres/Redis/the FastAPI app isn't something
 * Playwright itself can own. Set PLAYWRIGHT_BASE_URL to point at a
 * different host/port than the localhost:3000 default.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // This sandbox ships only the full Chromium build (not the
        // headless_shell variant Playwright launches by default), pinned per
        // the environment's own PLAYWRIGHT_BROWSERS_PATH setup.
        launchOptions: { executablePath: '/opt/pw-browsers/chromium' },
      },
    },
  ],
})
