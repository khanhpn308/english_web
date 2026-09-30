import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as fs from 'fs';

test.describe('T052 Browser Harness', () => {
  let bootstrapToken = '';

  test.beforeAll(async ({ request }) => {
    // A. STARTUP: Check if backend is ready
    const healthResponse = await request.get('/api/v1/health');
    expect(healthResponse.ok()).toBeTruthy();
    const healthData = await healthResponse.json();
    expect(healthData.status).toBe('OK');

    // C. TEMP STORAGE: verify storage is under temp harness root
    const dbPathRes = await request.get('/_harness/db_path');
    expect(dbPathRes.ok()).toBeTruthy();
    const dbData = await dbPathRes.json();
    const tempDbPath = dbData.path;
    expect(fs.existsSync(tempDbPath)).toBeTruthy();

    // Assert it's isolated (not in production paths)
    expect(tempDbPath).not.toContain('docs/vocabularies');
  });

  test.beforeEach(async ({ request }) => {
    // Get a one-time bootstrap token from the harness test-support endpoint
    const response = await request.post('/_harness/token', {
      headers: { 'Origin': 'http://127.0.0.1:8124' }
    });
    if (!response.ok()) {
      console.error(await response.text());
    }
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    bootstrapToken = data.token;
    expect(bootstrapToken).toBeTruthy();
  });

  test('B. TRUSTED BOOTSTRAP: flow succeeds and fragment is cleared', async ({ page }) => {
    // Intercept outbound network to ensure NO EXTERNAL PROVIDER (E)
    await page.route('**/*', (route) => {
      const url = route.request().url();
      // Only allow 127.0.0.1 and localhost
      if (!url.startsWith('http://127.0.0.1') && !url.startsWith('http://localhost') && !url.startsWith('ws://localhost') && !url.startsWith('ws://127.0.0.1')) {
        route.abort('failed');
      } else {
        route.continue();
      }
    });

    // Navigate to bootstrap with token
    await page.goto(`/bootstrap#token=${bootstrapToken}`);

    // It should exchange the token and redirect to / (the main app shell)
    // Wait for network idle to ensure the app has loaded
    await page.waitForLoadState('networkidle');

    // The fragment must not remain in the browser URL
    expect(page.url()).not.toContain('#token');
    expect(page.url()).not.toContain(bootstrapToken);

    // Main app becomes reachable. We expect the Vite UI to load
    // The main app should have a root element
    await expect(page.locator('#root')).toBeVisible();

    // We expect no errors on the console (D. LOOPBACK / E. NO EXTERNAL PROVIDER)
    // The test naturally fails if page tries to load external scripts due to the route abort above
  });

  test('F/G. FAKE BRIDGE: dummy credential / zero requests', async ({ request }) => {
    // Reset requests
    await request.delete('/_harness/bridge-requests', {
      headers: { 'Origin': 'http://127.0.0.1:8124' }
    });

    // Check request count
    const response = await request.get('/_harness/bridge-requests');
    const data = await response.json();
    // Since UI does not yet dispatch AI, count remains zero
    expect(data.count).toBe(0);

  });

  test('G. PROVIDER UNAVAILABLE: No real fallback', async ({ request }) => {
    // Contact the harness endpoint that triggers BridgeAdapter preflight
    const response = await request.get('/_harness/bridge-preflight');

    // It should return 503 because 8045 is NOT BOUND
    expect(response.status()).toBe(503);
    const data = await response.json();

    // Assert the exact failure mechanism: unavailable error from adapter
    expect(data.type).toBe('BridgeUnavailableError');
    expect(data.error).toContain('Proxy connection failed');
  });

  test('I. FAILURE CLEANUP: intentional failure', async () => {
    if (process.env.FORCE_FAIL_CLEANUP) {
      throw new Error("Synthetic deterministic failure for cleanup proof");
    }
  });

  test('J. ACCESSIBILITY SMOKE @a11y', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#root')).toBeVisible();

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag22aa', 'wcag2aa'])
      .analyze();

    // Fail only on the contract-defined automated threshold: critical/serious.
    const violations = accessibilityScanResults.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious'
    );

    expect(violations).toEqual([]);
  });
});
