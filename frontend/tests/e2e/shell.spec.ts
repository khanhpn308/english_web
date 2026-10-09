import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { build } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'path';
import type { components } from '../../src/shared/api/generated';

const shellWord = {
  id: 'wf-deep-link-test-999', lemma: 'robust', partOfSpeech: 'ADJECTIVE',
  meaningViMatch: 'vững chắc', verificationSummary: 'UNVERIFIED',
  noteDates: ['2026-10-09'], revision: 1, updatedAt: '2026-10-09T00:00:00Z',
} satisfies components['schemas']['WordFormSummary'];
const shellResults: components['schemas']['WordFormCollection'] = {
  data: [shellWord], pagination: { pageSize: 50, nextCursor: null, hasMore: false },
  sort: { by: 'relevance', direction: 'ASC' },
};
const shellDetail: components['schemas']['WordFormDetail'] = {
  ...shellWord, familyId: 'family_shell_synthetic',
  meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'VERIFIED' }],
  meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
  examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
  ipaUs: null, cambridgeUrl: null, card: null,
  sourceRefs: [{ sourceId: 'source_shell_synthetic', noteDate: '2026-10-09', status: 'VALID' }],
};

test.describe('T076 AppShell E2E & Visual Migration', () => {
  let bootstrapToken = '';
  let errorBoundaryHtml = '';

  test.beforeAll(async () => {
    // Build real mounted ErrorBoundary fixture bundle in-memory via Vite
    const res = await build({
      root: resolve(process.cwd(), 'frontend'),
      plugins: [
        react(),
        tailwindcss(),
        {
          name: 'virtual-eb-fixture',
          resolveId(id) {
            if (id === 'virtual:eb-fixture') return '\0virtual:eb-fixture.tsx';
          },
          load(id) {
            if (id === '\0virtual:eb-fixture.tsx') {
              return `
                import React, { useState } from 'react';
                import { createRoot } from 'react-dom/client';
                import { ErrorBoundary } from '@/app/AppShell';

                function BuggyChild({ shouldThrow }: { shouldThrow: boolean }) {
                  if (shouldThrow) {
                    throw new Error('Mô phỏng lỗi giao diện người dùng có thể thử lại');
                  }
                  return <div id="recovered-content" className="p-4 bg-muted text-foreground font-medium">Màn hình đã phục hồi thành công</div>;
                }

                function AppFixture() {
                  const [shouldThrow, setShouldThrow] = useState(true);
                  return (
                    <div className="p-6">
                      <button
                        id="disarm-error-btn"
                        className="mb-4 px-3 py-1 bg-secondary text-secondary-foreground rounded border text-sm"
                        onClick={() => setShouldThrow(false)}
                      >
                        Tắt trạng thái ném lỗi
                      </button>
                      <ErrorBoundary>
                        <BuggyChild shouldThrow={shouldThrow} />
                      </ErrorBoundary>
                    </div>
                  );
                }

                const root = createRoot(document.getElementById('root')!);
                root.render(<AppFixture />);
              `;
            }
          },
        },
      ],
      resolve: {
        alias: {
          '@': resolve(process.cwd(), 'frontend/src'),
        },
      },
      build: {
        write: false,
        rollupOptions: {
          input: 'virtual:eb-fixture',
        },
      },
      logLevel: 'silent',
    });

    const buildOutput = Array.isArray(res) ? res[0] : res;
    const output = (buildOutput as { output: Array<{ fileName: string; code?: string; source?: string | Uint8Array }> }).output;
    const jsChunk = output.find((c) => c.fileName.endsWith('.js'))?.code || '';
    const cssChunk = output.find((c) => c.fileName.endsWith('.css'))?.source || '';
    const cssText = typeof cssChunk === 'string' ? cssChunk : new TextDecoder().decode(cssChunk);

    errorBoundaryHtml = `
      <!DOCTYPE html>
      <html lang="vi">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>ErrorBoundary Fixture</title>
          <style>${cssText}</style>
        </head>
        <body>
          <div id="root"></div>
          <script type="module">${jsChunk}</script>
        </body>
      </html>
    `;
  });

  test.beforeEach(async ({ request, page }) => {
    // Intercept outbound network to guarantee no external requests occur
    await page.route('**/*', (route) => {
      const url = route.request().url();
      if (
        !url.startsWith('http://127.0.0.1') &&
        !url.startsWith('http://localhost') &&
        !url.startsWith('ws://localhost') &&
        !url.startsWith('ws://127.0.0.1')
      ) {
        route.abort('failed');
      } else {
        route.continue();
      }
    });

    // Obtain isolated synthetic session token from test support endpoint
    const response = await request.post('/_harness/token', {
      headers: { Origin: 'http://127.0.0.1:8124' },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    bootstrapToken = data.token;
    expect(bootstrapToken).toBeTruthy();
  });

  test('Skip link is keyboard-focusable, visually elevated, and targets main landmark', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    const skipLink = page.getByRole('link', { name: 'Chuyển đến nội dung chính' });
    await expect(skipLink).toBeAttached();

    // Tab into skip link
    await page.keyboard.press('Tab');
    await expect(skipLink).toBeFocused();

    // Verify elevated position and visible focus after transition completes (focus:top-4 -> 16px)
    await expect(skipLink).toHaveCSS('top', '16px');

    // Activating skip link with Enter moves focus to #main-content
    await page.keyboard.press('Enter');
    const mainContent = page.locator('#main-content');
    await expect(mainContent).toBeFocused();
  });

  test('Semantic landmarks and accessible names are properly structured', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // Landmarks
    const header = page.getByRole('banner');
    await expect(header).toBeVisible();

    const nav = page.getByRole('navigation', { name: 'Điều hướng chính' });
    await expect(nav).toBeVisible();

    const main = page.getByRole('main');
    await expect(main).toBeVisible();

    // Brand link in header
    const brandLink = header.getByRole('link', { name: 'Học Từ Vựng Học Thuật' });
    await expect(brandLink).toBeVisible();

    // AI consent quick link in header
    const consentLink = header.getByRole('link', { name: 'Quyền gửi dữ liệu AI' });
    await expect(consentLink).toBeVisible();
    expect(await consentLink.getAttribute('href')).toBe('/status#ai-consent');
  });

  test('Primary navigation updates URL, aria-current, polite live announcement, and focuses h1', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // Initial Dashboard state
    const dashboardLink = page.getByRole('link', { name: 'Tổng quan' });
    await expect(dashboardLink).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan' })).toBeVisible();

    // Navigate to Lookup
    const lookupLink = page.getByRole('link', { name: 'Tra cứu' });
    await lookupLink.click();

    expect(page.url()).toContain('/lookup');
    await expect(lookupLink).toHaveAttribute('aria-current', 'page');
    await expect(dashboardLink).not.toHaveAttribute('aria-current', 'page');

    const lookupHeading = page.getByRole('heading', { level: 1, name: 'Tra cứu từ vựng' });
    await expect(lookupHeading).toBeVisible();
    await expect(lookupHeading).toBeFocused();

    // Live region announces active screen
    const liveRegion = page.getByRole('status').filter({ hasText: 'Đang hiển thị màn hình' });
    await expect(liveRegion).toHaveCount(1);
    await expect(liveRegion).toContainText('Đang hiển thị màn hình Tra cứu từ vựng');

    // Navigate to Search
    const searchLink = page.getByRole('link', { name: 'Tìm kiếm' });
    await searchLink.click();

    expect(page.url()).toContain('/search');
    await expect(searchLink).toHaveAttribute('aria-current', 'page');
    const searchHeading = page.getByRole('heading', { level: 1, name: 'Tìm kiếm từ vựng' });
    await expect(searchHeading).toBeVisible();
    await expect(searchHeading).toBeFocused();
    await expect(liveRegion).toContainText('Đang hiển thị màn hình Tìm kiếm từ vựng');
    await expect(page.getByRole('region', { name: 'Tìm trong kho từ', exact: true })).toBeVisible();
    await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Duyệt kho từ', exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Thông báo trạng thái tính năng' })).toHaveCount(0);
  });

  test('Header brand link navigates to home dashboard, updates URL, renders overview, and focuses h1', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // 1. Navigate away from home to /lookup first
    const lookupLink = page.getByRole('link', { name: 'Tra cứu' });
    await lookupLink.click();
    expect(new URL(page.url()).pathname).toBe('/lookup');
    await expect(page.getByRole('heading', { level: 1, name: 'Tra cứu từ vựng' })).toBeVisible();

    // 2. Click brand link in header
    const brandLink = page.getByRole('banner').getByRole('link', { name: 'Học Từ Vựng Học Thuật' });
    await expect(brandLink).toBeVisible();
    await brandLink.click();

    // 3. Verify destination URL is home '/'
    expect(new URL(page.url()).pathname).toBe('/');

    // 4. Verify destination screen is Overview ('Tổng quan')
    const homeHeading = page.getByRole('heading', { level: 1, name: 'Tổng quan' });
    await expect(homeHeading).toBeVisible();

    // 5. Verify screen h1 receives focus after navigation per T004 contract
    await expect(homeHeading).toBeFocused();
  });

  test('Deep links, dynamic parameters, and browser back/forward history navigation', async ({ page }) => {
    // 1. Direct deep link with dynamic parameter: word-forms/:wordFormId
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    const detailReads: string[] = [];
    await page.route('**/api/v1/word-forms/wf-deep-link-test-999', async route => {
      expect(route.request().method()).toBe('GET');
      detailReads.push(new URL(route.request().url()).pathname);
      await route.fulfill({ json: shellDetail });
    });
    await page.goto('/word-forms/wf-deep-link-test-999');
    await page.waitForLoadState('networkidle');

    const wfHeading = page.getByRole('heading', { level: 1, name: 'Chi tiết từ vựng' });
    await expect(wfHeading).toBeVisible();
    const detail = page.getByRole('region', { name: 'Dạng từ đã lưu', exact: true });
    await expect(detail.getByRole('heading', { level: 2, name: 'robust', exact: true })).toBeVisible();
    await expect(detail.getByText('Nguồn hợp lệ', { exact: false })).toBeVisible();
    await expect(detail.getByText('Một thiết kế vững chắc.', { exact: true })).toBeVisible();
    await expect(detail.getByRole('link', { name: 'Quay lại kết quả tìm kiếm', exact: true })).toHaveAttribute('href', '/search');
    expect(detailReads.length).toBeGreaterThan(0);
    expect(detailReads.every(path => path === '/api/v1/word-forms/wf-deep-link-test-999')).toBe(true);
    await expect(page.getByRole('region', { name: 'Thông báo trạng thái tính năng' })).toHaveCount(0);

    // 2. Direct deep link with dynamic parameter: quiz/:attemptId
    await page.goto('/quiz/att-session-777');
    await page.waitForLoadState('networkidle');

    const quizHeading = page.getByRole('heading', { level: 1, name: 'Làm bài kiểm tra' });
    await expect(quizHeading).toBeVisible();
    await expect(page.getByText('att-session-777')).toBeVisible();

    // 3. Navigate between pages then exercise browser back and forward
    const reviewLink = page.getByRole('link', { name: 'Ôn tập' });
    await reviewLink.click();
    await expect(page.getByRole('heading', { level: 1, name: 'Ôn tập flashcard' })).toBeVisible();

    const statusLink = page.getByRole('link', { name: 'Trạng thái' });
    await statusLink.click();
    await expect(page.getByRole('heading', { level: 1, name: 'Trạng thái hệ thống & Quyền AI' })).toBeVisible();

    // Browser Back
    await page.goBack();
    await expect(page.getByRole('heading', { level: 1, name: 'Ôn tập flashcard' })).toBeVisible();

    // Browser Forward
    await page.goForward();
    await expect(page.getByRole('heading', { level: 1, name: 'Trạng thái hệ thống & Quyền AI' })).toBeVisible();
  });

  test('Keyboard navigation opens Search and Word Detail and restores URL state through history and reload', async ({ page }) => {
    const reads: URL[] = [];
    await page.route(/\/api\/v1\/word-forms(?:\/[^/?]+)?(?:\?.*)?$/, async route => {
      const url = new URL(route.request().url());
      expect(route.request().method()).toBe('GET');
      reads.push(url);
      if (url.pathname === '/api/v1/word-forms') {
        await route.fulfill({ json: shellResults });
      } else if (url.pathname === '/api/v1/word-forms/wf-deep-link-test-999') {
        await route.fulfill({ json: shellDetail });
      } else {
        throw new Error('Unexpected word-form read');
      }
    });
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    const nav = page.getByRole('navigation', { name: 'Điều hướng chính', exact: true });
    const searchLink = nav.getByRole('link', { name: 'Tìm kiếm', exact: true });
    await searchLink.focus();
    await expect(searchLink).toBeFocused();
    await page.keyboard.press('Enter');
    const searchHeading = page.getByRole('heading', { level: 1, name: 'Tìm kiếm từ vựng', exact: true });
    await expect(searchHeading).toBeFocused();
    await expect(searchLink).toHaveAttribute('aria-current', 'page');
    expect(reads).toEqual([]);
    await page.keyboard.press('Tab');
    const meaning = page.getByRole('searchbox', { name: 'Nghĩa tiếng Việt', exact: true });
    await expect(meaning).toBeFocused();
    await page.keyboard.insertText('vững chắc');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('searchbox', { name: 'Dạng từ / lemma', exact: true })).toBeFocused();
    const results = page.getByRole('list', { name: 'Kết quả tìm kiếm', exact: true });
    const result = results.getByRole('link', { name: 'robust', exact: true });
    await expect(result).toBeVisible();
    const searchUrl = page.url();
    expect(new URL(searchUrl).searchParams.get('meaningVi')).toBe('vững chắc');
    expect(reads.at(-1)?.searchParams.get('meaningVi')).toBe('vững chắc');
    await result.focus();
    await expect(result).toBeFocused();
    await page.keyboard.press('Enter');
    const detailHeading = page.getByRole('heading', { level: 1, name: 'Chi tiết từ vựng', exact: true });
    await expect(detailHeading).toBeFocused();
    await expect(page.getByRole('heading', { level: 2, name: 'robust', exact: true })).toBeVisible();
    const detailUrl = page.url();
    expect(new URL(detailUrl).searchParams.get('returnTo')).toBe(new URL(searchUrl).pathname + new URL(searchUrl).search);
    await expect(page.getByRole('region', { name: 'Nguồn và ngày ghi chú', exact: true })).toContainText('Nguồn hợp lệ');
    await page.reload();
    await expect(detailHeading).toBeFocused();
    await page.keyboard.press('Tab');
    const back = page.getByRole('link', { name: 'Quay lại kết quả tìm kiếm', exact: true });
    await expect(back).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(searchUrl);
    await expect(searchHeading).toBeFocused();
    await expect(meaning).toHaveValue('vững chắc');
    await expect(result).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(detailUrl);
    await expect(detailHeading).toBeFocused();
    await page.goForward();
    await expect(page).toHaveURL(searchUrl);
    await expect(searchHeading).toBeFocused();
    await expect(meaning).toHaveValue('vững chắc');
    await page.reload();
    await expect(meaning).toHaveValue('vững chắc');
    await expect(result).toBeVisible();
    await expect(searchLink).toHaveAttribute('aria-current', 'page');
  });

  test('404 Not Found view renders accessible error message and recovers to home via Button with h1 focus', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // Trigger client-side navigation to an unmatched route
    await page.evaluate(() => {
      window.history.pushState(null, '', '/a-route-that-does-not-exist');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    const notFoundHeading = page.getByRole('heading', { level: 1, name: 'Không tìm thấy trang' });
    await expect(notFoundHeading).toBeVisible();
    await expect(page.getByText('Địa chỉ bạn yêu cầu không tồn tại hoặc đã được thay đổi.')).toBeVisible();

    // Recovery action via Button primitive
    const returnHomeBtn = page.getByRole('link', { name: 'Quay lại trang chủ' });
    await expect(returnHomeBtn).toBeVisible();
    await returnHomeBtn.click();

    // Should return to Dashboard: assert URL, screen heading, and h1 focus
    expect(new URL(page.url()).pathname).toBe('/');
    const homeHeading = page.getByRole('heading', { level: 1, name: 'Tổng quan' });
    await expect(homeHeading).toBeVisible();
    await expect(homeHeading).toBeFocused();
  });

  test('ErrorBoundary fallback catches error, renders accessible retry Card, and recovers rendered UI upon user activation', async ({ page }) => {
    // 1. Mount real ErrorBoundary fixture
    await page.setContent(errorBoundaryHtml);
    await page.waitForLoadState('domcontentloaded');

    // 2. Verify fallback UI rendered with role="alert" and assertive live region
    const alertCard = page.locator('[role="alert"]');
    await expect(alertCard).toBeVisible();
    await expect(page.getByRole('heading', { level: 2, name: 'Đã xảy ra lỗi không mong muốn' })).toBeVisible();
    await expect(page.getByText('Mô phỏng lỗi giao diện người dùng có thể thử lại')).toBeVisible();

    // 3. Exposes the rendered retry control and status link
    const retryBtn = alertCard.getByRole('button', { name: 'Thử lại màn hình này' });
    await expect(retryBtn).toBeVisible();
    const statusLink = alertCard.getByRole('link', { name: 'Kiểm tra trạng thái hệ thống' });
    await expect(statusLink).toBeVisible();
    await expect(page.locator('#recovered-content')).not.toBeAttached();

    // 4. Disarm error throwing on next render (simulating underlying condition resolved)
    await page.locator('#disarm-error-btn').click();

    // 5. Activate the actual rendered retry button
    await retryBtn.click();

    // 6. Verify fallback UI disappears and recovered normal content is rendered and visible
    await expect(page.locator('#recovered-content')).toBeVisible();
    await expect(page.locator('#recovered-content')).toContainText('Màn hình đã phục hồi thành công');
    await expect(alertCard).not.toBeAttached();
  });

  test('Header AI consent quick link preserves href markup and navigates to status', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    const consentQuickLink = page.getByRole('banner').getByRole('link', { name: 'Quyền gửi dữ liệu AI' });
    await expect(consentQuickLink).toBeVisible();
    expect(await consentQuickLink.getAttribute('href')).toBe('/status#ai-consent');

    await consentQuickLink.click();

    // Client-side router navigates to /status screen view
    expect(new URL(page.url()).pathname).toBe('/status');
    const statusHeading = page.getByRole('heading', { level: 1, name: 'Trạng thái hệ thống & Quyền AI' });
    await expect(statusHeading).toBeVisible();
    await expect(statusHeading).toBeFocused();
  });

  test('Automated accessibility scan passes with zero critical or serious violations @a11y', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#root')).toBeVisible();

    // Scan home dashboard view
    const dashboardScan = await new AxeBuilder({ page })
      .withTags(['wcag22aa', 'wcag2aa'])
      .analyze();

    const dashboardViolations = dashboardScan.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(dashboardViolations).toEqual([]);

    // Navigate to 404 view via client-side routing and scan
    await page.evaluate(() => {
      window.history.pushState(null, '', '/unknown-a11y-check');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await expect(page.getByRole('heading', { level: 1, name: 'Không tìm thấy trang' })).toBeVisible();

    const notFoundScan = await new AxeBuilder({ page })
      .withTags(['wcag22aa', 'wcag2aa'])
      .analyze();

    const notFoundViolations = notFoundScan.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(notFoundViolations).toEqual([]);
  });

  test('Responsive layout renders without horizontal overflow across configured viewport widths', async ({ page }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // Test representative widths: 320 (WCAG SC 1.4.10 mobile baseline), 768, 1024, 1440
    const viewports = [
      { width: 320, height: 568 },
      { width: 768, height: 1024 },
      { width: 1024, height: 768 },
      { width: 1440, height: 900 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);
      // Ensure content fits within viewport without horizontal scrolling
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth;
      });
      expect(hasHorizontalScroll).toBe(false);
    }
  });

  test('200% effective-layout equivalent (640px) reflow verification without horizontal overflow or loss of functionality', async ({ page }) => {
    // Effective layout viewport of 640px represents a nominal 1280px desktop condition at 200% zoom
    await page.setViewportSize({ width: 640, height: 800 });
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // A. Verify no unintended page-level horizontal overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // B. Header and navigation controls remain visible, wrapped, reachable, operable
    const header = page.getByRole('banner');
    await expect(header).toBeVisible();
    const nav = page.getByRole('navigation', { name: 'Điều hướng chính' });
    await expect(nav).toBeVisible();
    const brandLink = header.getByRole('link', { name: 'Học Từ Vựng Học Thuật' });
    await expect(brandLink).toBeVisible();

    // Verify nav links wrap appropriately without overflowing header
    const navItems = page.getByRole('navigation', { name: 'Điều hướng chính' }).getByRole('link');
    const navCount = await navItems.count();
    expect(navCount).toBeGreaterThanOrEqual(4);
    for (let i = 0; i < navCount; i++) {
      await expect(navItems.nth(i)).toBeVisible();
    }

    // C. Keyboard focus remains usable and visible across critical controls
    await page.keyboard.press('Tab'); // Skip link
    const skipLink = page.getByRole('link', { name: 'Chuyển đến nội dung chính' });
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toBeVisible();

    // D. 404 recovery control wrapping & reachability under 640px effective layout
    await page.evaluate(() => {
      window.history.pushState(null, '', '/not-found-reflow-probe');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    const notFoundHeading = page.getByRole('heading', { level: 1, name: 'Không tìm thấy trang' });
    await expect(notFoundHeading).toBeVisible();
    const returnHomeBtn = page.getByRole('link', { name: 'Quay lại trang chủ' });
    await expect(returnHomeBtn).toBeVisible();

    // Check no horizontal overflow on 404 screen
    const notFoundOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(notFoundOverflow).toBe(false);

    // Button wraps text if needed and remains operable
    await returnHomeBtn.click();
    await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan' })).toBeVisible();
  });

  test('CDP visual viewport magnification diagnostic check (pageScaleFactor 2.0)', async ({ page, context }) => {
    await page.goto(`/bootstrap#token=${bootstrapToken}`);
    await page.waitForLoadState('networkidle');

    // Set standard desktop viewport 1280x800
    await page.setViewportSize({ width: 1280, height: 800 });

    // Diagnostic check: Chrome DevTools Protocol (CDP) session sets visual page scale factor to 2.0.
    // Note: This tests visual viewport magnification (visualViewport = 640px within 1280px CSS layout viewport),
    // distinct from layout viewport reflow tested separately under 640px effective layout.
    const cdp = await context.newCDPSession(page);
    await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2.0 });

    const visualMetrics = await page.evaluate(() => {
      const vv = window.visualViewport;
      return {
        innerWidth: window.innerWidth,
        visualWidth: vv ? Math.round(vv.width) : 0,
        scale: vv ? Math.round(vv.scale) : 1,
        hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
      };
    });

    expect(visualMetrics.innerWidth).toBe(1280);
    expect(visualMetrics.visualWidth).toBe(640);
    expect(visualMetrics.scale).toBe(2);
    expect(visualMetrics.hasHorizontalOverflow).toBe(false);

    // Detach CDP session
    await cdp.detach();
  });
});
