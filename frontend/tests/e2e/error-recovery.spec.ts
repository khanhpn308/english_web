import { test, expect } from '@playwright/test';

test.describe('Error Recovery E2E', () => {
  // Common setup would go here, maybe navigating to a page where RecoveryPanel is mounted,
  // or testing the actual lookup UI that uses it.
  
  test('retains user draft on network failure and allows retry', async ({ page }) => {
    // Navigate to lookup page
    await page.goto('/');
    
    // Fill draft
    const input = page.getByPlaceholder(/search/i);
    await input.fill('test draft');
    
    // Intercept API to simulate network failure
    await page.route('/api/v1/lookups', route => route.abort('failed'));
    
    await page.getByRole('button', { name: /search/i }).click();
    
    // Should show network error
    await expect(page.getByText('Cannot Reach Server')).toBeVisible();
    
    // Draft should be retained
    await expect(input).toHaveValue('test draft');
    
    // Recover by retry
    await page.route('/api/v1/lookups', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          LookupResult: { status: 'PREVIEW' }
        })
      });
    });
    
    await page.getByRole('button', { name: /Retry Action/i }).click();
    
    // Success state should appear
    await expect(page.getByText('Cannot Reach Server')).not.toBeVisible();
  });

  test('distinguishes bridge stopped vs api stopped', async ({ page }) => {
    await page.goto('/');
    
    // Simulate API stopped
    await page.route('/api/v1/lookups', route => route.abort('failed'));
    await page.getByPlaceholder(/search/i).fill('test');
    await page.getByRole('button', { name: /search/i }).click();
    await expect(page.getByText('Cannot Reach Server')).toBeVisible();

    // Simulate Bridge unavailable
    await page.route('/api/v1/lookups', async route => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'BRIDGE_UNAVAILABLE',
            message: 'Bridge is down',
            requestId: 'req_123'
          }
        })
      });
    });
    
    await page.getByRole('button', { name: /Retry Action/i }).click();
    await expect(page.getByText('AI Bridge Unavailable')).toBeVisible();
  });

  test('handles session expiration', async ({ page }) => {
    await page.goto('/');
    
    await page.route('/api/v1/lookups', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'SESSION_INVALID',
            message: 'Expired',
            requestId: 'req_123'
          }
        })
      });
    });
    
    await page.getByPlaceholder(/search/i).fill('test');
    await page.getByRole('button', { name: /search/i }).click();
    
    await expect(page.getByText('Session Expired')).toBeVisible();
    await expect(page.getByRole('button', { name: /Log In Again/i })).toBeVisible();
  });

  test('handles revision conflict and prompts reload', async ({ page }) => {
    await page.goto('/');
    
    await page.route('/api/v1/lookups', async route => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'REVISION_CONFLICT',
            message: 'Conflict',
            requestId: 'req_123'
          }
        })
      });
    });
    
    await page.getByPlaceholder(/search/i).fill('test');
    await page.getByRole('button', { name: /search/i }).click();
    
    await expect(page.getByText('Conflict')).toBeVisible();
    await expect(page.getByRole('button', { name: /Reload Content/i })).toBeVisible();
  });

  test('handles unknown mutation outcome without blind retry', async ({ page }) => {
    await page.goto('/');
    
    // For mutation, use POST to simulate save
    // Normally would trigger a save action. We simulate this by intercepting lookups for now, assuming lookups is POST.
    let requests = 0;
    await page.route('/api/v1/lookups', async route => {
      requests++;
      if (requests === 1) {
        // Abort to simulate lost response AFTER request is sent (playwright abort before is tricky, but aborting simulates connection drop)
        // Wait, if it's aborted, `apiClient` maps it to MutationUnknownError for POST
        route.abort('failed');
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ LookupResult: { status: 'PREVIEW' } })
        });
      }
    });
    
    await page.getByPlaceholder(/search/i).fill('test');
    await page.getByRole('button', { name: /search/i }).click();
    
    // Should show Connection Lost, not generic Network Error because it's a POST
    await expect(page.getByText('Connection Lost')).toBeVisible();
    
    // Reconcile button
    await expect(page.getByRole('button', { name: /Check Status/i })).toBeVisible();
  });
});
