import { test, expect, type BrowserContext, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type Collection = components['schemas']['WordFormCollection'];
type Detail = components['schemas']['WordFormDetail'];
const word = { id: 'form_synthetic', lemma: 'robust', partOfSpeech: 'ADJECTIVE', meaningViMatch: 'vững chắc; đáng tin cậy', noteDates: ['2026-10-09'], revision: 1, updatedAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED' } satisfies Collection['data'][number];
const collection = (data: Collection['data'] = [word], nextCursor: string | null = null): Collection => ({ data, pagination: { nextCursor, pageSize: 50, hasMore: nextCursor !== null }, sort: { by: 'relevance', direction: 'ASC' } });
const detail: Detail = { ...word, familyId: 'family_synthetic', meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'VERIFIED' }], meaningsVi: [{ text: 'vững chắc; đáng tin cậy', language: 'vi', verificationStatus: 'UNVERIFIED' }], examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }], ipaUs: '/roʊˈbʌst/', cambridgeUrl: null, sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'VALID' }], card: null };
const fail = (route: Route, code: string, status = 503) => route.fulfill({ status, json: { error: { code, message: 'private backend exception', requestId: 'req_synthetic' } } });

// Boundary fixtures use the real T052 shell/bootstrap. No external traffic or AI.
async function fixture(context: BrowserContext) {
  const reads: URL[] = [];
  const forbidden: string[] = [];
  let list: (route: Route, url: URL) => Promise<void> = async route => { await route.fulfill({ json: collection() }); };
  let form: (route: Route) => Promise<void> = async route => { await route.fulfill({ json: detail }); };
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:8124') { forbidden.push(url.origin); await route.abort(); return; }
    if (url.pathname.startsWith('/api/v1/') && route.request().method() !== 'GET') { forbidden.push(url.pathname); await route.abort(); return; }
    if (url.pathname === '/api/v1/word-forms') { reads.push(url); await list(route, url); return; }
    if (url.pathname.startsWith('/api/v1/word-forms/')) { await form(route); return; }
    await route.continue();
  });
  return { reads, forbidden, list: (handler: typeof list) => { list = handler; }, form: (handler: typeof form) => { form = handler; } };
}

test.beforeEach(async ({ page, request }) => {
  const response = await request.post('/_harness/token', { headers: { Origin: 'http://127.0.0.1:8124' } });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  await page.goto(`/bootstrap#token=${body.token}`);
  await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan', exact: true })).toBeVisible();
});

test('explicit browse, supported filters, URL restoration and history', async ({ page, context }) => {
  const api = await fixture(context);
  await page.goto('/search');
  await expect(page.getByText('Nhập nghĩa tiếng Việt hoặc dạng từ', { exact: false })).toBeVisible();
  expect(api.reads).toHaveLength(0);
  await page.getByRole('button', { name: 'Duyệt kho từ', exact: true }).click();
  await expect(page.getByRole('link', { name: 'robust', exact: true })).toBeVisible();
  await page.getByLabel('Nghĩa tiếng Việt', { exact: true }).fill('vững chắc');
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('robust');
  await page.getByLabel('Loại từ', { exact: true }).selectOption('ADJECTIVE');
  await page.getByLabel('Xác minh', { exact: true }).selectOption('UNVERIFIED');
  await page.getByLabel('Ngày ghi chú', { exact: true }).fill('2026-10-09');
  await page.getByLabel('Trạng thái nguồn', { exact: true }).selectOption('VALID');
  await page.getByLabel('Sắp xếp', { exact: true }).selectOption('lemma');
  await page.getByLabel('Thứ tự', { exact: true }).selectOption('DESC');
  await page.getByLabel('Số kết quả mỗi trang', { exact: true }).selectOption('20');
  const search = page.url();
  await page.reload();
  await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toHaveValue('vững chắc');
  await expect(page.getByLabel('Trạng thái nguồn', { exact: true })).toHaveValue('VALID');
  await expect(page.getByLabel('Số kết quả mỗi trang', { exact: true })).toHaveValue('20');
  await expect.poll(() => api.reads.at(-1)?.searchParams.get('sortOrder')).toBe('DESC');
  const sent = api.reads.at(-1)!.searchParams;
  expect(Object.fromEntries(sent)).toEqual({ meaningVi: 'vững chắc', lemma: 'robust', partOfSpeech: 'ADJECTIVE', verificationStatus: 'UNVERIFIED', noteDate: '2026-10-09', sourceStatus: 'VALID', sortBy: 'lemma', sortOrder: 'DESC', pageSize: '20' });
  await page.getByRole('link', { name: 'robust', exact: true }).click();
  await expect(page).toHaveURL(/\/word-forms\/form_synthetic/);
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
  await expect(page.getByText('Nguồn hợp lệ', { exact: false })).toBeVisible();
  await expect(page.getByText('Một thiết kế vững chắc.', { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole('link', { name: 'Quay lại kết quả tìm kiếm' }).click();
  await expect(page).toHaveURL(search);
  await page.goBack(); await expect(page).toHaveURL(/\/word-forms\/form_synthetic/);
  await page.goForward(); await expect(page).toHaveURL(search);
  await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toHaveValue('vững chắc');
  expect(api.forbidden).toEqual([]);
});

test('literal question marks survive direct query loading and reload', async ({ page, context }) => {
  const api = await fixture(context);
  await page.goto('/search?meaningVi=a?b&sourceStatus=VALID');
  await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toHaveValue('a?b');
  await page.reload();
  await expect.poll(() => api.reads.at(-1)?.searchParams.get('meaningVi')).toBe('a?b');
  expect(api.reads.at(-1)?.searchParams.get('sourceStatus')).toBe('VALID');
});

test('next-page cursor, expired cursor restart and preserved query', async ({ page, context }) => {
  const api = await fixture(context);
  let expired = false;
  api.list(async (route, url) => {
    if (url.searchParams.has('cursor')) {
      if (expired) { await fail(route, 'CURSOR_EXPIRED', 409); return; }
      await route.fulfill({ json: collection([{ ...word, id: 'form_next', lemma: 'resilient' }], 'cursor_next') }); return;
    }
    await route.fulfill({ json: collection([word], 'cursor_first') });
  });
  await page.goto('/search?meaningVi=vững&pageSize=20');
  await page.getByRole('button', { name: 'Trang tiếp', exact: true }).click();
  await expect(page.getByRole('link', { name: 'resilient', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/cursor=cursor_first/);
  expired = true;
  await page.getByRole('button', { name: 'Trang tiếp', exact: true }).click();
  await expect(page.getByText('Trang đã hết hạn', { exact: false })).toBeVisible();
  expect(new URL(page.url()).searchParams.has('cursor')).toBe(false);
  await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toHaveValue('vững');
  await expect(page.getByRole('link', { name: 'robust', exact: true })).toBeVisible();
});

test('empty results and backend stopped while frontend remains active', async ({ page, context }) => {
  const api = await fixture(context);
  api.list(async route => { await route.fulfill({ json: collection([]) }); });
  await page.goto('/search?lemma=robust');
  await expect(page.getByText('Không tìm thấy dạng từ phù hợp.', { exact: false })).toBeVisible();
  api.list(async route => { await route.abort('connectionrefused'); });
  await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Cannot Reach Server');
  await expect(page.getByText('Không tìm thấy dạng từ phù hợp.', { exact: false })).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tìm kiếm từ vựng');
  api.list(async route => { await route.fulfill({ json: collection() }); });
  await page.getByRole('button', { name: 'Retry Action', exact: true }).click();
  await expect(page.getByRole('link', { name: 'robust', exact: true })).toBeVisible();
  await expect(page.getByLabel('Dạng từ / lemma', { exact: true })).toHaveValue('robust');
});

test('rapid changes hide stale results when old response is delayed', async ({ page, context }) => {
  const api = await fixture(context);
  let release!: () => void;
  let arrived!: () => void;
  const oldStarted = new Promise<void>(resolve => { arrived = resolve; });
  const oldGate = new Promise<void>(resolve => { release = resolve; });
  let finished!: () => void;
  const oldFinished = new Promise<void>(resolve => { finished = resolve; });
  api.list(async (route, url) => {
    if (url.searchParams.get('lemma') === 'old') { arrived(); await oldGate; await route.fulfill({ json: collection([{ ...word, lemma: 'stale' }]) }); finished(); return; }
    await route.fulfill({ json: collection([{ ...word, lemma: 'current' }]) });
  });
  // Start the read after mount so StrictMode's initial effect probe is idle.
  await page.goto('/search');
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('old'); await oldStarted;
  await expect(page.getByText('Đang tải kết quả…')).toBeVisible();
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('current');
  await expect(page.getByRole('link', { name: 'current', exact: true })).toBeVisible();
  release();
  await oldFinished;
  await expect(page.getByRole('link', { name: 'stale', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'current', exact: true }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'robust', exact: true })).toBeVisible();
});

test('A -> B -> A keeps newest A while obsolete A and B finish later', async ({ page, context }) => {
  const api = await fixture(context);
  const pending: { route: Route; term: string; release: () => void }[] = [];
  api.list(async (route, url) => {
    const term = url.searchParams.get('lemma') ?? '';
    await new Promise<void>(resolve => { pending.push({ route, term, release: resolve }); });
  });
  await page.goto('/search');
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('A');
  await expect.poll(() => pending.length).toBe(1);
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('B');
  await expect.poll(() => pending.length).toBe(2);
  await page.getByLabel('Dạng từ / lemma', { exact: true }).fill('A');
  await expect.poll(() => pending.length).toBe(3);
  expect(pending.map(item => item.term)).toEqual(['A', 'B', 'A']);
  await pending[2].route.fulfill({ json: collection([{ ...word, lemma: 'newest A' }]) }); pending[2].release();
  await expect(page.getByRole('link', { name: 'newest A', exact: true })).toBeVisible();
  await pending[1].route.fulfill({ json: collection([{ ...word, lemma: 'stale B' }]) }); pending[1].release();
  await pending[0].route.fulfill({ json: collection([{ ...word, lemma: 'stale A' }]) }); pending[0].release();
  await expect(page.getByRole('link', { name: 'newest A', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /^stale/ })).toHaveCount(0);
});

for (const status of ['INVALID', 'MISSING'] as const) {
  test(`detail shows ${status} source health`, async ({ page, context }) => {
    const api = await fixture(context);
    api.form(async route => { await route.fulfill({ json: { ...detail, sourceRefs: [{ ...detail.sourceRefs[0], status }], verificationSummary: 'MISSING' } satisfies Detail }); });
    await page.goto('/word-forms/form_synthetic');
    await expect(page.getByRole('alert')).toContainText('Không có nguồn hợp lệ');
    await expect(page.getByText('2026-10-09', { exact: true })).toBeVisible();
    await expect(page.getByText('Một thiết kế vững chắc.', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 2, name: 'Nghĩa', exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 2, name: 'Ví dụ', exact: true })).toHaveCount(0);
    await expect(page.getByText(status === 'INVALID' ? 'Nguồn không hợp lệ' : 'Nguồn không còn tồn tại', { exact: false })).toBeVisible();
  });
}

test('malformed JSON search and detail successes remain recoverable', async ({ page, context }) => {
  const api = await fixture(context);
  api.list(async route => { await route.fulfill({ json: { data: null } }); });
  await page.goto('/search?lemma=robust');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByText('Đang tải kết quả…')).toHaveCount(0);
  api.list(async route => { await route.fulfill({ json: collection() }); });
  await page.getByRole('button', { name: 'Retry Action', exact: true }).click();
  await expect(page.getByRole('link', { name: 'robust', exact: true })).toBeVisible();
  api.form(async route => { await route.fulfill({ json: { ...detail, sourceRefs: null } }); });
  await page.getByRole('link', { name: 'robust', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByText('Đang tải chi tiết…')).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 2, name: 'Đã xảy ra lỗi không mong muốn', exact: true })).toHaveCount(0);
  api.form(async route => { await route.fulfill({ json: detail }); });
  await page.getByRole('button', { name: 'Retry Action', exact: true }).click();
  await expect(page.getByText('Một thiết kế vững chắc.', { exact: true })).toBeVisible();
  expect(api.forbidden).toEqual([]);
});

for (const [code, title] of [['NOT_FOUND', 'Không tìm thấy dạng từ'], ['STORAGE_UNAVAILABLE', 'Storage Unavailable'], ['SESSION_INVALID', 'Session Expired'], ['SOURCE_INVALID', 'Nguồn không hợp lệ']] as const) {
  test(`safe detail recovery for ${code}`, async ({ page, context }) => {
    const api = await fixture(context);
    api.form(async route => { await fail(route, code, code === 'NOT_FOUND' ? 404 : 503); });
    await page.goto('/word-forms/form_synthetic?returnTo=%2Fsearch%3FmeaningVi%3Dvững');
    await expect(page.getByRole('alert')).toContainText(title);
    await expect(page.getByText('private backend exception', { exact: false })).toHaveCount(0);
    await page.getByRole('link', { name: 'Quay lại kết quả tìm kiếm' }).click();
    await expect(page.getByLabel('Nghĩa tiếng Việt', { exact: true })).toHaveValue('vững');
  });
}

test('keyboard, long Vietnamese text, responsive reflow and accessibility @a11y', async ({ page, context }) => {
  const api = await fixture(context);
  api.list(async route => { await route.fulfill({ json: collection([{ ...word, meaningViMatch: 'nghĩa tiếng Việt rất dài '.repeat(40), lemma: 'synthetic'.repeat(30) }]) }); });
  await page.goto('/search?browse=1');
  const link = page.getByRole('list', { name: 'Kết quả tìm kiếm' }).getByRole('link');
  await expect(link).toBeVisible();
  await page.getByLabel('Nghĩa tiếng Việt', { exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Dạng từ / lemma', { exact: true })).toBeFocused();
  for (const width of [320, 640]) {
    // 640px is the existing harness's 200% effective desktop reflow scenario.
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await link.focus(); await expect(link).toBeFocused();
  }
  const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
  expect(scan.violations.filter(item => item.impact === 'critical' || item.impact === 'serious')).toEqual([]);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
  await expect(page.getByRole('heading', { level: 2, name: 'robust', exact: true })).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Quay lại kết quả tìm kiếm', exact: true })).toBeFocused();
  const detailScan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
  expect(detailScan.violations.filter(item => item.impact === 'critical' || item.impact === 'serious')).toEqual([]);
  expect(api.forbidden).toEqual([]);
});
