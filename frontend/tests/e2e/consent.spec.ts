import { test, expect, type BrowserContext, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type View = components['schemas']['AiConsentView'];
const policy: NonNullable<View['policy']> = {
  version: 'synthetic-policy-v1', digest: 'a'.repeat(64), reviewStatus: 'READY',
  disclosureText: 'Synthetic disclosure. No provider assurances.',
  recipients: ['Synthetic recipient'], dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'],
  retentionStatement: 'Synthetic retention limitation', regionStatement: 'Synthetic region limitation',
  costQuotaStatement: 'Synthetic entitlement and quota limitation', withdrawalStatement: 'Synthetic withdrawal limitation',
  scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [],
  dispatchRules: (['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'] as const).map(scope => ({
    scope, providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account',
  })),
};
function snapshot(state: View['state'] = 'NOT_GRANTED', revision = 0): View {
  return { state, revision, policy, acceptedPolicyVersion: state === 'GRANTED' ? policy.version : null,
    acceptedPolicyDigest: state === 'GRANTED' ? policy.digest : null, canRequestAi: state === 'GRANTED',
    lastChoiceAt: revision ? '2026-10-08T00:00:00Z' : null };
}
async function fixture(context: BrowserContext) {
  let current = snapshot();
  let etag = '"synthetic-0"';
  const mutations: { method: string; key: string | undefined; etag: string | undefined; body: string | null }[] = [];
  const forbidden: string[] = [];
  let handler: ((route: Route) => Promise<void>) | null = null;
  let readHandler: ((route: Route) => Promise<void>) | null = null;
  const receipts = new Map<string, { appliedRevision: number; operationId: string }>();
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname) || /\/api\/v1\/(lookups|quiz-attempts|feedback)/.test(url.pathname)) {
      forbidden.push(url.pathname); await route.abort(); return;
    }
    if (url.pathname !== '/api/v1/ai-consent') { await route.continue(); return; }
    const request = route.request();
    if (request.method() === 'GET') {
      if (readHandler) { await readHandler(route); return; }
      await route.fulfill({ json: current, headers: { ETag: etag, 'Cache-Control': 'no-store' } }); return;
    }
    const headers = request.headers();
    mutations.push({ method: request.method(), key: headers['idempotency-key'], etag: headers['if-match'], body: request.postData() });
    if (handler) { await handler(route); return; }
    const key = headers['idempotency-key'];
    const prior = receipts.get(key);
    if (prior) { await route.fulfill({ json: prior }); return; }
    if (request.method() === 'PUT' && headers['if-match'] !== etag) {
      await route.fulfill({ status: 409, json: { error: { code: 'REVISION_CONFLICT', message: 'Synthetic stale tab', requestId: 'req_synthetic' } } }); return;
    }
    current = snapshot(request.method() === 'DELETE' ? 'REVOKED' : 'GRANTED', current.revision + 1);
    etag = `"synthetic-${current.revision}"`;
    const receipt = { appliedRevision: current.revision, operationId: `op_synthetic_${current.revision}` };
    receipts.set(key, receipt); await route.fulfill({ json: receipt });
  });
  return {
    mutations, forbidden, read: () => current,
    update: (value: View) => { current = value; etag = `"synthetic-${value.revision}-${value.policy?.digest}"`; },
    mutationHandler: (value: ((route: Route) => Promise<void>) | null) => { handler = value; },
    readHandler: (value: ((route: Route) => Promise<void>) | null) => { readHandler = value; },
  };
}
async function status(page: Page) {
  await page.goto('/status');
  await expect(page.locator('#ai-consent')).toContainText('NOT_GRANTED');
}
async function grant(page: Page) {
  await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
  await page.getByRole('button', { name: 'Đồng ý', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.locator('#ai-consent')).toContainText('GRANTED');
}

test.describe('T018 consent in the application shell', () => {
  test.beforeEach(async ({ page, request }) => {
    const token = await request.post('/_harness/token', { headers: { Origin: 'http://127.0.0.1:8124' } });
    expect(token.ok()).toBeTruthy();
    const data = await token.json();
    await page.goto(`/bootstrap#token=${data.token}`);
    await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan' })).toBeVisible();
  });

  test('keyboard disclosure, trapped focus, Escape decline, focus restoration and local navigation', async ({ page, context }) => {
    const backend = await fixture(context);
    await page.getByRole('link', { name: 'Quyền gửi dữ liệu AI', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('NOT_GRANTED');
    const trigger = page.getByRole('button', { name: 'Xem chính sách AI', exact: true });
    await trigger.focus(); await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Quyền gửi dữ liệu AI' })).toBeFocused();
    for (const value of [policy.version, policy.digest, ...policy.dataCategories, ...policy.scopes,
      ...policy.recipients, policy.retentionStatement, policy.regionStatement, policy.costQuotaStatement,
      policy.withdrawalStatement, 'Antigravity/Google', 'gemini-3.8-flash-high', 'primary', 'configured-account']) {
      await expect(dialog).toContainText(value);
    }
    for (let index = 0; index < 8; index += 1) {
      await page.keyboard.press('Tab');
      expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(trigger).toBeFocused();
    await trigger.press('Space'); await page.getByRole('button', { name: 'Chưa đồng ý', exact: true }).click();
    expect(backend.mutations).toHaveLength(0);
    await page.getByRole('link', { name: 'Ôn tập', exact: true }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Ôn tập flashcard' })).toBeVisible();
    expect(backend.forbidden).toEqual([]);
  });

  test('explicit grant and bridge-down revoke cause zero learning requests', async ({ page, context, request }) => {
    const backend = await fixture(context); await status(page); await grant(page);
    expect(backend.mutations).toHaveLength(1);
    expect(JSON.parse(backend.mutations[0].body ?? '')).toEqual({ policyVersion: policy.version });
    expect(backend.mutations[0].etag).toBe('"synthetic-0"');
    // Existing harness proves the bridge is unavailable; consent never depends on it.
    expect((await request.get('/_harness/bridge-preflight')).status()).toBe(503);
    await page.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    await expect(page.locator('#ai-consent')).toContainText('Đã chặn các yêu cầu AI mới');
    expect(backend.mutations[1].etag).toBeUndefined(); expect(backend.mutations[1].body).toBeNull();
    await expect(page.locator('#ai-consent')).toContainText('Yêu cầu đã gửi có thể vẫn hoàn tất');
    expect(backend.forbidden).toEqual([]);
  });

  test('two tabs invalidate cached grant and reject stale grant without overwriting revoke', async ({ page, context }) => {
    const backend = await fixture(context); await status(page);
    const second = await context.newPage(); await second.goto('/status');
    await expect(second.locator('#ai-consent')).toContainText('NOT_GRANTED');
    await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
    await second.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    await expect(second.locator('#ai-consent')).toContainText('REVOKED');
    await expect(page.locator('#ai-consent')).toContainText('REVOKED');
    // Cross-tab invalidation requires disclosure to be read again before grant.
    await expect(page.getByRole('button', { name: 'Đồng ý', exact: true })).toBeDisabled();
    expect(backend.read().state).toBe('REVOKED');
    await page.keyboard.press('Escape');
    await grant(second);
    await expect(page.locator('#ai-consent')).toContainText('GRANTED');
    await second.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    await expect(page.locator('#ai-consent')).toContainText('REVOKED');
    expect(backend.forbidden).toEqual([]); await second.close();
  });

  test('focus refresh detects new policy and same-version digest corruption', async ({ page, context }) => {
    const backend = await fixture(context); await status(page); await grant(page);
    backend.update({ ...backend.read(), policy: { ...policy, digest: 'b'.repeat(64) } });
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.locator('#ai-consent')).toContainText('STALE');
    await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('Chưa hoàn tất chính sách AI');
    await expect(page.getByRole('button', { name: 'Đồng ý', exact: true })).toHaveCount(0);
    await page.keyboard.press('Escape');
    backend.update({ ...snapshot('STALE', 1), policy: { ...policy, version: 'synthetic-policy-v2', digest: 'c'.repeat(64) } });
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('synthetic-policy-v2');
    await expect(page.getByRole('button', { name: 'Đồng ý', exact: true })).toBeEnabled();
    expect(backend.mutations).toHaveLength(1); expect(backend.forbidden).toEqual([]);
  });

  test('lost response reconciles durable revoke; failed revoke remains unresolved and uses the same key', async ({ page, context }) => {
    const backend = await fixture(context); await status(page); await grant(page);
    backend.mutationHandler(async route => { await route.abort('failed'); });
    await page.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    await expect(page.locator('#ai-consent')).toContainText('Chưa xác nhận rút quyền');
    await expect(page.locator('#ai-consent')).toContainText('Các thao tác AI mới đang bị tắt');
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.locator('#ai-consent')).toContainText('Chưa xác nhận rút quyền');
    backend.mutationHandler(async route => { backend.update(snapshot('REVOKED', 2)); await route.abort('failed'); });
    await page.getByRole('button', { name: 'Thử lại cùng thao tác' }).click();
    await expect(page.locator('#ai-consent')).toContainText('Đã chặn các yêu cầu AI mới');
    expect(backend.mutations[1].key).toBe(backend.mutations[2].key);
    expect(backend.forbidden).toEqual([]);
  });

  test('historical receipt does not restore consent; missing policy still permits revoke', async ({ page, context }) => {
    const backend = await fixture(context); await status(page);
    backend.mutationHandler(async route => {
      backend.update({ ...snapshot('REVOKED', 2), policy: null });
      await route.fulfill({ json: { operationId: 'op_historical', appliedRevision: 1 } });
    });
    await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
    await page.getByRole('button', { name: 'Đồng ý', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('REVOKED');
    await page.keyboard.press('Escape');
    await expect(page.locator('#ai-consent')).toContainText('Chưa hoàn tất chính sách AI');
    await page.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    expect(backend.mutations.at(-1)?.method).toBe('DELETE'); expect(backend.forbidden).toEqual([]);
  });

  test('loading and typed read errors preserve the shell and recover without consent writes', async ({ page, context }) => {
    const backend = await fixture(context);
    let release!: () => void;
    const held = new Promise<void>(resolve => { release = resolve; });
    backend.readHandler(async route => {
      await held;
      await route.fulfill({ status: 503, json: { error: { code: 'STORAGE_BUSY', message: 'Synthetic failure', requestId: 'req_synthetic' } } });
    });
    await page.goto('/status', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#ai-consent')).toContainText('Đang đọc quyền AI');
    await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toBeVisible();
    release();
    await expect(page.locator('#ai-consent')).toContainText('STORAGE_BUSY');
    await expect(page.locator('#ai-consent')).toContainText('req_synthetic');
    backend.readHandler(null);
    await page.getByRole('button', { name: 'Đọc lại trạng thái' }).click();
    await expect(page.locator('#ai-consent')).toContainText('NOT_GRANTED');
    expect(backend.mutations).toHaveLength(0); expect(backend.forbidden).toEqual([]);
  });

  test('consent panel and dialog have no serious accessibility violations and reflow @a11y', async ({ page, context }) => {
    const backend = await fixture(context); await status(page);
    for (const width of [320, 640, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    }
    for (const dialogOpen of [false, true]) {
      if (dialogOpen) await page.getByRole('button', { name: 'Xem chính sách AI', exact: true }).click();
      const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
      expect(scan.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
    }
    await page.setViewportSize({ width: 320, height: 568 });
    const agree = page.getByRole('button', { name: 'Đồng ý', exact: true });
    await agree.scrollIntoViewIfNeeded(); await expect(agree).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    expect(backend.forbidden).toEqual([]);
  });
});
