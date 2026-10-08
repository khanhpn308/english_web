import { test, expect, type BrowserContext, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type View = components['schemas']['AiConsentView'];
type Preview = components['schemas']['LookupResult'];
type Operation = components['schemas']['Operation'];
const policy: NonNullable<View['policy']> = {
  version: 'synthetic-policy-v1', digest: 'a'.repeat(64), reviewStatus: 'READY',
  disclosureText: 'Synthetic disclosure', recipients: ['Synthetic recipient'],
  dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'], retentionStatement: 'Synthetic retention',
  regionStatement: 'Synthetic region', costQuotaStatement: 'Synthetic quota', withdrawalStatement: 'Synthetic withdrawal',
  scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [],
  dispatchRules: (['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'] as const).map(scope => ({
    scope, providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account',
  })),
};
function snapshot(state: View['state'] = 'GRANTED', revision = 1): View {
  return { state, revision, policy, canRequestAi: state === 'GRANTED',
    acceptedPolicyVersion: state === 'GRANTED' ? policy.version : null,
    acceptedPolicyDigest: state === 'GRANTED' ? policy.digest : null,
    lastChoiceAt: revision ? '2026-10-09T00:00:00Z' : null };
}
function preview(): Preview {
  return { lookupId: 'lookup_synthetic', operationId: 'op_synthetic', term: 'robust', status: 'PREVIEW',
    provider: 'Antigravity/Google', model: 'gemini-3.8-flash-high', promptVersion: 'lookup-v1',
    createdAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED',
    forms: [{ formId: 'draft_synthetic', lemma: 'robust', partOfSpeech: 'ADJECTIVE',
      ipaUs: '/roʊˈbʌst/', ipaStatus: 'VERIFIED',
      cambridgeUrl: 'https://dictionary.cambridge.org/dictionary/english/robust', cambridgeStatus: 'UNVERIFIED',
      meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'UNVERIFIED' }],
      meaningsVi: [{ text: 'vững chắc; đáng tin cậy', language: 'vi', verificationStatus: 'UNVERIFIED' }],
      examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
      verificationSummary: 'UNVERIFIED' }],
  };
}
async function fail(route: Route, code: string, operationId?: string, status = 503) {
  await route.fulfill({ status, json: { error: { code, message: 'Synthetic private provider details', requestId: 'req_synthetic',
    ...(operationId ? { details: { kind: 'RETRY', operationId } } : {}) } } });
}

// Reuse the T052 real shell/bootstrap server and T018 boundary fixture convention.
// Boundary fixtures retain the existing UI failure/recovery cases. The isolated
// real-API scenarios below continue every API request to the production routes.
async function fixture(context: BrowserContext, initial = snapshot()) {
  let consent = initial;
  let lookupHandler: (route: Route) => Promise<void> = async route => { await route.fulfill({ json: preview() }); };
  let operationStatus: Operation['status'] = 'UNKNOWN';
  const posts: { body: string | null; key: string | undefined; requestId: string | undefined }[] = [];
  const forbidden: string[] = [];
  const consentWrites: string[] = [];
  let operationReads = 0;
  let realLookup = false;
  await context.route('**/*', async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== 'http://127.0.0.1:8124') { forbidden.push(url.pathname); await route.abort(); return; }
    if (url.pathname === '/api/v1/ai-consent') {
      if (request.method() === 'GET') {
        await route.fulfill({ json: consent, headers: { ETag: `"synthetic-${consent.revision}"`, 'Cache-Control': 'no-store' } });
      } else {
        consentWrites.push(request.method());
        consent = snapshot(request.method() === 'PUT' ? 'GRANTED' : 'REVOKED', consent.revision + 1);
        await route.fulfill({ json: { operationId: 'op_consent', appliedRevision: consent.revision } });
      }
      return;
    }
    if (url.pathname === '/api/v1/lookups') {
      expect(request.method()).toBe('POST');
      posts.push({ body: request.postData(), key: request.headers()['idempotency-key'], requestId: request.headers()['x-request-id'] });
      if (realLookup) { await route.continue(); return; }
      await lookupHandler(route); return;
    }
    if (url.pathname === '/api/v1/operations/op_synthetic') {
      expect(request.method()).toBe('GET'); operationReads += 1;
      await route.fulfill({ json: { operationId: 'op_synthetic', kind: 'LOOKUP', status: operationStatus,
        createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z',
        ...(operationStatus === 'SUCCEEDED' ? { resultRef: 'lookup_synthetic' } : {}) } satisfies Operation }); return;
    }
    if (url.pathname.startsWith('/api/v1/') && request.method() !== 'GET') {
      forbidden.push(url.pathname); await route.abort(); return;
    }
    await route.continue();
  });
  return { posts, forbidden, consentWrites, reads: () => operationReads,
    consent: (value: View) => { consent = value; },
    lookup: (handler: (route: Route) => Promise<void>) => { lookupHandler = handler; },
    realLookup: () => { realLookup = true; },
    operation: (value: Operation['status']) => { operationStatus = value; } };
}
async function enter(page: Page, term = 'robust') {
  await page.goto('/lookup');
  await expect(page.getByRole('heading', { level: 1, name: 'Tra cứu từ vựng' })).toBeVisible();
  await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill(term);
}

async function realFixture(page: Page, context: BrowserContext, scenario = 'preview') {
  const forbidden: string[] = [];
  const posts: { body: string | null; key: string | undefined; requestId: string | undefined }[] = [];
  const consentWrites: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:8124') {
      forbidden.push(url.pathname); await route.abort(); return;
    }
    await route.continue();
  });
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path === '/api/v1/lookups' && request.method() === 'POST') {
      posts.push({ body: request.postData(), key: request.headers()['idempotency-key'], requestId: request.headers()['x-request-id'] });
    } else if (path === '/api/v1/ai-consent' && request.method() !== 'GET') {
      consentWrites.push(request.method());
    } else if (path.startsWith('/api/v1/') && request.method() !== 'GET') {
      forbidden.push(path);
    }
  });
  // page.request shares the browser's cookie jar. Each setup owns a fresh real
  // app, SQLite database and fake bridge, even with concurrent viewport projects.
  const setup = await page.request.post('/_harness/lookup-session', {
    headers: { Origin: 'http://127.0.0.1:8124' }, data: { scenario },
  });
  expect(setup.ok()).toBeTruthy();
  const token = await setup.json();
  await page.goto(`/bootstrap#token=${token.token}`);
  await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan' })).toBeVisible();
  const state = async () => {
    const response = await page.request.get('/_harness/lookup-state');
    expect(response.ok()).toBeTruthy(); return response.json();
  };
  return { posts, consentWrites, forbidden, state };
}

test.describe('T009 lookup through the real application route', () => {
  test.beforeEach(async ({ page, request }) => {
    const token = await request.post('/_harness/token', { headers: { Origin: 'http://127.0.0.1:8124' } });
    expect(token.ok()).toBeTruthy(); const data = await token.json();
    await page.goto(`/bootstrap#token=${data.token}`);
    await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan' })).toBeVisible();
  });

  test('idle and invalid input cause zero POST requests and focus the invalid field', async ({ page, context }) => {
    const backend = await fixture(context); await enter(page, '');
    await expect(page.locator('#lookup-status')).toContainText('Nhập từ'); expect(backend.posts).toHaveLength(0);
    for (const term of ['', '   ', 'a'.repeat(81)]) {
      const input = page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }); await input.fill(term);
      await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
      await expect(input).toHaveAttribute('aria-invalid', 'true'); await expect(input).toBeFocused();
      await expect(input).toHaveValue(term);
    }
    expect(backend.posts).toHaveLength(0); expect(backend.forbidden).toEqual([]);
  });

  test('decline, Escape, grant and route restoration preserve draft and never dispatch', async ({ page, context }) => {
    const backend = await fixture(context, snapshot('NOT_GRANTED', 0)); await enter(page, '  robust  ');
    const action = page.getByRole('button', { name: 'Tra cứu', exact: true });
    await action.focus(); await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog').getByRole('heading', { name: 'Quyền gửi dữ liệu AI' })).toBeFocused();
    await page.keyboard.press('Escape'); await expect(action).toBeFocused(); expect(backend.posts).toHaveLength(0);
    await action.click(); await page.getByRole('button', { name: 'Chưa đồng ý', exact: true }).click();
    expect(backend.posts).toHaveLength(0); expect(backend.consentWrites).toHaveLength(0);
    await action.click(); await page.getByRole('button', { name: 'Đồng ý', exact: true }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible(); expect(backend.posts).toHaveLength(0);
    await page.getByRole('link', { name: 'Trạng thái', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('GRANTED');
    await page.getByRole('link', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true })).toHaveValue('  robust  ');
    expect(backend.posts).toHaveLength(0);
    await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).press('Enter');
    await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả');
    expect(backend.posts).toHaveLength(1); expect(JSON.parse(backend.posts[0].body ?? '')).toEqual({ term: 'robust' });
    expect(backend.posts[0].key).toBeTruthy(); expect(backend.posts[0].requestId).toBeTruthy(); expect(backend.forbidden).toEqual([]);
  });

  test('full preview uses safe text, source labels and no persistence requests', async ({ page, context }) => {
    const backend = await fixture(context); const data = preview();
    data.forms.push({ ...data.forms[0], formId: 'draft_other', lemma: 'robustly', partOfSpeech: 'ADVERB', ipaUs: null, ipaStatus: 'MISSING' });
    data.forms[0].meaningsVi.push({ text: '<img src=x onerror=alert(1)>', language: 'vi', verificationStatus: 'UNVERIFIED' });
    data.forms[1].cambridgeUrl = 'javascript:alert(1)';
    backend.lookup(async route => { await route.fulfill({ json: data }); });
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toBeFocused();
    for (const value of ['robustly', 'ADVERB', 'ADJECTIVE', 'vững chắc; đáng tin cậy', 'A robust design.',
      'Một thiết kế vững chắc.', '/roʊˈbʌst/', 'MISSING', 'UNVERIFIED', '<img src=x onerror=alert(1)>', 'Chỉ xem trước']) {
      await expect(page.getByRole('region', { name: 'Tra cứu và xem trước' })).toContainText(value);
    }
    const source = page.getByRole('link', { name: /dictionary.cambridge.org\/dictionary\/english\/robust/ });
    await expect(source).toHaveAttribute('rel', 'noopener noreferrer'); await expect(source).toHaveAttribute('referrerpolicy', 'no-referrer');
    expect(await page.locator('main img, main script, main a[href^="javascript:"]').count()).toBe(0);
    await page.getByText('Nguồn gốc kết quả', { exact: true }).click();
    await expect(page.getByRole('region', { name: 'Tra cứu và xem trước' })).toContainText('lookup-v1');
    expect(backend.posts).toHaveLength(1); expect(backend.forbidden).toEqual([]);
    await page.getByRole('link', { name: 'Ôn tập', exact: true }).click(); expect(backend.posts).toHaveLength(1);
  });

  test('held response, obsolete edits, lost response and empty preview', async ({ page, context }) => {
    const backend = await fixture(context);
    let release!: () => void; const held = new Promise<void>(resolve => { release = resolve; });
    backend.lookup(async route => { await held; await route.fulfill({ json: preview() }); });
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Đang tra cứu');
    await expect(page.getByRole('button', { name: 'Tra cứu', exact: true })).toBeDisabled();
    await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill('different');
    release(); await expect(page.locator('#lookup-status')).toContainText('Nội dung nhập đã thay đổi');
    await expect(page.getByRole('heading', { name: /Kết quả xem trước/ })).toHaveCount(0);
    expect(backend.posts).toHaveLength(1);
    const empty = { ...preview(), term: 'different', forms: [] };
    backend.lookup(async route => { await route.fulfill({ json: empty }); });
    await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Không có dạng từ'); expect(backend.posts).toHaveLength(2);
    backend.lookup(async route => { await route.abort('failed'); });
    await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Chưa xác định'); expect(backend.posts).toHaveLength(3);
    expect(backend.forbidden).toEqual([]);
  });

  test('unknown receipt only reads until terminal, then explicit retry uses a new key', async ({ page, context }) => {
    const backend = await fixture(context); backend.lookup(route => fail(route, 'BRIDGE_UNAVAILABLE', 'op_synthetic'));
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Chưa xác định');
    for (const status of ['PENDING', 'UNKNOWN'] as const) {
      backend.operation(status); await page.getByRole('button', { name: 'Kiểm tra kết quả' }).click();
      await expect(page.locator('#lookup-status')).toContainText('Chưa xác định'); expect(backend.posts).toHaveLength(1);
    }
    backend.operation('FAILED'); await page.getByRole('button', { name: 'Kiểm tra kết quả' }).click();
    await expect(page.locator('#lookup-status')).toContainText('Thao tác đã thất bại');
    backend.lookup(async route => { await route.fulfill({ json: preview() }); });
    await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả');
    expect(backend.posts).toHaveLength(2); expect(backend.posts[0].key).not.toBe(backend.posts[1].key);
    expect(backend.reads()).toBe(3); expect(backend.forbidden).toEqual([]);
  });

  test('lost response explicit recovery retains the key and body across term edits', async ({ page, context }) => {
    const backend = await fixture(context); backend.lookup(async route => { await route.abort('failed'); });
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Chưa xác định');
    await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill('other');
    backend.lookup(async route => { await route.fulfill({ json: preview() }); });
    await page.getByRole('button', { name: 'Kiểm tra kết quả' }).click();
    await expect(page.locator('#lookup-status')).toContainText('Nội dung nhập đã thay đổi');
    expect(backend.posts).toHaveLength(2); expect(backend.posts[0]).toEqual(backend.posts[1]);
    await expect(page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true })).toHaveValue('other');
    expect(backend.forbidden).toEqual([]);
  });

  test('revocation while pending and focus reconciliation never create another lookup', async ({ page, context }) => {
    const backend = await fixture(context);
    let release!: () => void; const held = new Promise<void>(resolve => { release = resolve; });
    backend.lookup(async route => { await held; await route.fulfill({ json: preview() }); });
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('Đang tra cứu');
    await page.getByRole('link', { name: 'Trạng thái', exact: true }).click();
    await page.getByRole('button', { name: 'Rút lại quyền gửi dữ liệu AI' }).click();
    await expect(page.locator('#ai-consent')).toContainText('REVOKED'); release();
    await page.getByRole('link', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true })).toHaveValue('robust');
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả'); expect(backend.posts).toHaveLength(1);
    await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible(); expect(backend.posts).toHaveLength(1); expect(backend.forbidden).toEqual([]);
  });

  test('malformed preview and unavailable API remain unknown without false success', async ({ page, context }) => {
    const backend = await fixture(context); backend.lookup(async route => { await route.fulfill({ json: { ...preview(), forms: [{}] } }); });
    await enter(page); await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.locator('#lookup-status')).toContainText('phản hồi không hợp lệ');
    backend.lookup(async route => { await route.fulfill({ status: 503, contentType: 'text/plain', body: 'Synthetic unavailable API' }); });
    await page.getByRole('button', { name: 'Kiểm tra kết quả' }).click();
    await expect(page.locator('#lookup-status')).toContainText('Chưa xác định');
    await expect(page.getByRole('heading', { name: /Kết quả xem trước/ })).toHaveCount(0);
    expect(backend.posts).toHaveLength(2); expect(backend.posts[0].key).toBe(backend.posts[1].key); expect(backend.forbidden).toEqual([]);
  });

  test('real T008 API denies mock-only consent before upstream and preserves local vocabulary', async ({ page, context }) => {
    const backend = await fixture(context); backend.realLookup();
    const before = await page.request.get('/api/v1/word-forms'); expect(before.ok()).toBeTruthy();
    const beforeWords = await before.json();
    const beforeBridge = await page.request.get('/_harness/bridge-requests'); expect(beforeBridge.ok()).toBeTruthy();
    const beforeCount = await beforeBridge.json();
    await enter(page);
    const denied = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/lookups');
    await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    const response = await denied; expect(response.status()).toBe(403);
    expect((await response.json()).error.code).toBe('AI_CONSENT_REQUIRED');
    await expect(page.locator('#lookup-status')).toContainText('Quyền AI đã thay đổi');
    await expect(page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true })).toHaveValue('robust');
    const after = await page.request.get('/api/v1/word-forms'); expect(after.ok()).toBeTruthy();
    expect(await after.json()).toEqual(beforeWords);
    const afterBridge = await page.request.get('/_harness/bridge-requests'); expect(afterBridge.ok()).toBeTruthy();
    expect(await afterBridge.json()).toEqual(beforeCount);
    expect(backend.posts).toHaveLength(1); expect(backend.forbidden).toEqual([]);
  });

  test('real API grants consent without dispatch, then keyboard lookup creates only a preview', async ({ page, context }) => {
    const backend = await realFixture(page, context);
    const before = await backend.state();
    expect(before).toMatchObject({ wordForms: 0, sources: 0, cards: 0, previews: 0,
      admissions: 0, bridge: { count: 0, lookupDispatches: 0, requests: [] } });
    const consent = await page.request.get('/api/v1/ai-consent');
    expect(consent.ok()).toBeTruthy(); expect(consent.headers()['etag']).toBeTruthy();
    expect(await consent.json()).toMatchObject({ state: 'NOT_GRANTED', revision: 0,
      canRequestAi: false, policy: { reviewStatus: 'READY' } });
    // A real direct API attempt also fails before preflight, even with READY policy.
    const denied = await page.request.post('/api/v1/lookups', {
      headers: { Origin: 'http://127.0.0.1:8124', 'Idempotency-Key': 'synthetic-denied-lookup' },
      data: { term: 'robust' },
    });
    expect(denied.status()).toBe(403);
    expect((await denied.json()).error).toMatchObject({ code: 'AI_CONSENT_REQUIRED',
      details: { kind: 'AI_CONSENT', consentState: 'NOT_GRANTED' } });
    expect((await backend.state()).bridge).toEqual(before.bridge);

    await page.getByRole('link', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Tra cứu từ vựng' })).toBeFocused();
    const input = page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true });
    const action = page.getByRole('button', { name: 'Tra cứu', exact: true });
    await input.fill('  robust  '); await input.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Quyền gửi dữ liệu AI' })).toBeFocused();
    await expect(dialog).toContainText('Synthetic lookup disclosure');
    await dialog.getByRole('button', { name: 'Chưa đồng ý', exact: true }).press('Enter');
    await expect(dialog).not.toBeVisible(); await expect(input).toHaveValue('  robust  ');
    expect(backend.posts).toHaveLength(0); expect(backend.consentWrites).toEqual([]);
    expect((await backend.state()).bridge).toEqual(before.bridge);

    await action.focus(); await page.keyboard.press('Enter');
    await expect(dialog).toBeVisible();
    const granted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/ai-consent' && response.request().method() === 'PUT');
    await dialog.getByRole('button', { name: 'Đồng ý', exact: true }).press('Enter');
    expect((await granted).status()).toBe(200);
    await expect(dialog).not.toBeVisible(); await expect(input).toHaveValue('  robust  ');
    expect(backend.consentWrites).toEqual(['PUT']); expect(backend.posts).toHaveLength(0);
    await page.getByRole('link', { name: 'Trạng thái', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('GRANTED');
    expect((await backend.state()).bridge).toEqual(before.bridge);
    await page.getByRole('link', { name: 'Tra cứu', exact: true }).click();
    await expect(input).toHaveValue('  robust  '); expect(backend.posts).toHaveLength(0);

    const lookup = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/lookups' && response.request().method() === 'POST');
    await input.press('Enter');
    const response = await lookup; expect(response.status()).toBe(200);
    const result: Preview = await response.json();
    expect(result).toMatchObject({ status: 'PREVIEW', term: 'robust', promptVersion: 'lookup-v1',
      provider: 'Antigravity/Google', model: 'gemini-3.8-flash-high' });
    expect(result.forms).toHaveLength(2);
    expect(result.forms[0]).toMatchObject({ lemma: 'robust', ipaUs: '/rəˈbʌst/',
      ipaStatus: 'UNVERIFIED', cambridgeStatus: 'UNVERIFIED',
      meaningsEn: [{ text: 'able to work effectively', language: 'en', verificationStatus: 'UNVERIFIED' }],
      meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
      examples: [{ english: 'The design is robust.', vietnamese: 'Thiết kế rất vững chắc.', verificationStatus: 'UNVERIFIED' }],
    });
    expect(result.forms[1]).toMatchObject({ lemma: 'robustly', ipaUs: null, ipaStatus: 'MISSING' });
    const status = page.locator('#lookup-status');
    await expect(status).toHaveText('Đã có kết quả xem trước. Chưa lưu từ hoặc tạo thẻ.');
    await expect(status).toHaveAttribute('role', 'status');
    await expect(status).toHaveAttribute('aria-live', 'polite');
    await expect(status).toHaveAttribute('aria-atomic', 'true'); await expect(status).toBeFocused();
    const previewRegion = page.getByRole('region', { name: 'Tra cứu và xem trước' });
    for (const form of result.forms) {
      await expect(previewRegion.getByRole('heading', { level: 3, name: form.lemma, exact: true })).toBeVisible();
      await expect(previewRegion).toContainText(form.partOfSpeech);
      for (const meaning of [...form.meaningsEn, ...form.meaningsVi]) {
        expect(meaning.verificationStatus).toBe('UNVERIFIED');
        await expect(previewRegion).toContainText(meaning.text);
      }
      for (const example of form.examples) {
        expect(example.verificationStatus).toBe('UNVERIFIED');
        await expect(previewRegion).toContainText(example.english);
        await expect(previewRegion).toContainText(example.vietnamese);
      }
    }
    for (const label of ['MISSING · Thiếu dữ liệu', 'UNVERIFIED · Chưa xác minh', 'Không có IPA Mỹ', 'Chỉ xem trước']) {
      await expect(previewRegion).toContainText(label);
    }
    await expect(previewRegion).toContainText(result.forms[0].ipaUs!);
    const source = previewRegion.getByRole('link', { name: /dictionary.cambridge.org/ });
    await expect(source).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(source).toHaveAttribute('referrerpolicy', 'no-referrer');
    const provenance = previewRegion.getByText('Nguồn gốc kết quả', { exact: true });
    await provenance.focus(); await provenance.press('Enter');
    await expect(previewRegion).toContainText(result.lookupId);
    expect(backend.posts).toHaveLength(1);
    expect(JSON.parse(backend.posts[0].body ?? '')).toEqual({ term: 'robust' });
    expect(backend.posts[0].key).toBeTruthy(); expect(backend.posts[0].requestId).toBeTruthy();
    const after = await backend.state();
    expect(after).toMatchObject({ wordForms: 0, sources: 0, cards: 0, previews: 1, admissions: 1,
      bridge: { count: 3, lookupDispatches: 1, transport: 'in-process-asgi' } });
    expect(after.bridge.requests).toEqual([
      { method: 'GET', url: '/v1/models', auth: false },
      { method: 'GET', url: '/v1/models', auth: true },
      { method: 'POST', url: '/v1/chat/completions', auth: true,
        model: 'gemini-3.8-flash-high', promptVersion: 'lookup-v1', fixture: 'robust', scenario: 'preview' },
    ]);
    const receipt = await page.request.get(`/api/v1/operations/${result.operationId}`);
    expect(receipt.ok()).toBeTruthy();
    expect(await receipt.json()).toMatchObject({ kind: 'LOOKUP', status: 'SUCCEEDED', resultRef: result.lookupId });
    const replay = await page.request.post('/api/v1/lookups', {
      headers: { Origin: 'http://127.0.0.1:8124', 'Idempotency-Key': backend.posts[0].key! }, data: { term: 'robust' },
    });
    expect(replay.status()).toBe(200); expect(await replay.json()).toEqual(result);
    await page.getByRole('link', { name: 'Ôn tập', exact: true }).click();
    expect(await backend.state()).toEqual(after);
    expect(backend.posts).toHaveLength(1); expect(backend.forbidden).toEqual([]);
  });

  test('real malformed upstream output fails without preview or automatic retry', async ({ page, context }) => {
    const backend = await realFixture(page, context, 'invalid-response');
    await enter(page);
    await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).press('Enter');
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('button', { name: 'Đồng ý', exact: true }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible(); expect(backend.posts).toHaveLength(0);
    const failed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/lookups');
    await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).press('Enter');
    const response = await failed; expect(response.status()).toBe(502);
    expect((await response.json()).error.code).toBe('BRIDGE_INVALID_RESPONSE');
    await expect(page.locator('#lookup-status')).toHaveAttribute('role', 'alert');
    await expect(page.locator('#lookup-status')).toBeFocused();
    await expect(page.getByRole('heading', { name: /Kết quả xem trước/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Thử lại', exact: true })).toBeEnabled();
    expect(await backend.state()).toMatchObject({ previews: 0, wordForms: 0, sources: 0, cards: 0,
      admissions: 1, bridge: { lookupDispatches: 1, transport: 'in-process-asgi' } });
    await page.getByRole('link', { name: 'Trạng thái', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('GRANTED');
    expect(backend.posts).toHaveLength(1); expect((await backend.state()).bridge.lookupDispatches).toBe(1);
    expect(backend.forbidden).toEqual([]);
  });

  test('same-version policy drift only blocks lookup and never submits the term', async ({ page, context }) => {
    const backend = await fixture(context); await enter(page);
    // Establish current policy evidence through the real consent panel.
    await page.getByRole('link', { name: 'Trạng thái', exact: true }).click();
    await expect(page.locator('#ai-consent')).toContainText('GRANTED');
    backend.consent({ ...snapshot(), policy: { ...policy, digest: 'b'.repeat(64) } });
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.locator('#ai-consent')).toContainText('STALE');
    await page.getByRole('link', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true })).toHaveValue('robust');
    expect(backend.posts).toHaveLength(0);
    await page.getByRole('button', { name: 'Tra cứu', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('Chưa hoàn tất chính sách AI');
    expect(backend.posts).toHaveLength(0); expect(backend.forbidden).toEqual([]);
  });

  test('preview reflows and has no serious accessibility violations @a11y', async ({ page, context }) => {
    const backend = await fixture(context); const data = preview(); data.forms[0].meaningsVi[0].text = 'Tiếng Việt dài '.repeat(80);
    backend.lookup(async route => { await route.fulfill({ json: data }); });
    await enter(page); await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).press('Enter');
    await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả');
    for (const width of [320, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    }
    const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
    expect(scan.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
    expect(backend.posts).toHaveLength(1); expect(backend.forbidden).toEqual([]);
  });
});
