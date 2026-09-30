import { defineConfig, devices } from '@playwright/test';

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './frontend/tests/e2e',
  /* Maximum time one test can run for. */
  timeout: 30 * 1000,
  expect: {
    /**
     * Maximum time expect() should wait for the condition to be met.
     */
    timeout: 5000
  },
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only, locally prefer deterministic failure */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'list',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: 'http://127.0.0.1:8124',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Sanitize artifacts: do not record video or full DOM snapshots containing user data */
    video: 'off',
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium-1440',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 }
      },
    },
    {
      name: 'chromium-1024',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1024, height: 768 }
      },
    },
    {
      name: 'chromium-768',
      use: {
        browserName: 'chromium',
        viewport: { width: 768, height: 1024 }
      },
    },
    {
      name: 'chromium-320',
      use: {
        browserName: 'chromium',
        viewport: { width: 320, height: 568 }
      },
    },
    // Windows Microsoft Edge channel: explicit PENDING unless available
    // We conditionally add it if it's explicitly requested, or keep it as pending.
    // Playwright fails immediately if the channel is not available.
    // According to T052: "explicit PENDING unless available in the current environment; do not mark PASS without running it."
    /*
    {
      name: 'Microsoft Edge',
      use: { ...devices['Desktop Edge'], channel: 'msedge' },
    },
    */
  ],

  webServer: process.env.HANG_FIXTURE ? {
    command: 'python3 -m http.server 8129',
    url: 'http://127.0.0.1:8129/not-found',
    reuseExistingServer: false,
    timeout: 2000,
  } : {
    command: 'PYTHONPATH=. ../vocabularies-t062/.venv/bin/python frontend/tests/support/test_server.py --port 8124',
    url: 'http://127.0.0.1:8124/api/v1/health',
    reuseExistingServer: !process.env.CI,
    timeout: 10 * 1000,
  },
});
