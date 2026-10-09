import { test, expect, type BrowserContext, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type Card = components['schemas']['ReviewCardView'];
type Queue = components['schemas']['ReviewQueueView'];
type Detail = components['schemas']['WordFormDetail'];
type Event = components['schemas']['ReviewEventView'];
type Operation = components['schemas']['Operation'];
const card = (id = 'one', revision = 7): Card => ({ cardId: `card_${id}`, wordFormId: `form_${id}`,
  lemma: id === 'one' ? 'robust' : 'precise', queueRevision: revision, state: 'NEW', dueAt: null, noteDates: ['2026-10-09'] });
const queue = (data = [card()]): Queue => ({ data, pagination: { pageSize: 50, hasMore: false, nextCursor: null },
  sort: { by: 'dueAt', direction: 'ASC' } });
const detail = (item: Card): Detail => ({ id: item.wordFormId, familyId: 'family_synthetic', lemma: item.lemma,
  partOfSpeech: 'ADJECTIVE', revision: 1, updatedAt: '2026-10-09T00:00:00Z', ipaUs: null, cambridgeUrl: null,
  verificationSummary: 'UNVERIFIED', meaningsEn: [],
  meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
  examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
  sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'VALID' }],
  card: { id: item.cardId, state: item.state, dueAt: item.dueAt } });
const event = (rating: Event['rating']): Event => ({ id: 'event_synthetic', cardId: 'card_one', rating, source: 'FLASHCARD',
  operationId: 'op_synthetic', reviewedAt: '2026-10-09T00:00:00Z', nextDueAt: '2026-10-22T17:00:00Z' });
async function failure(route: Route, code: string, operationId?: string, status = 409) {
  await route.fulfill({ status, json: { error: { code, message: 'Synthetic private details', requestId: 'req_synthetic',
    ...(operationId ? { details: { kind: 'RETRY', operationId } } : {}) } } });
}
// T052 serves the real shell and bootstrap. Only local API boundaries are replaced
// with generated-contract fixtures; every external request is refused.
async function fixture(context: BrowserContext) {
  let cards = [card()];
  let mutation: (route: Route) => Promise<void> = async route => {
    const rating = route.request().postDataJSON().rating as Event['rating'];
    cards = [card('two', 12)]; await route.fulfill({ status: 201, json: event(rating) });
  };
  let operation: Operation['status'] = 'UNKNOWN';
  const posts: { body: string | null; key: string | undefined; revision: string | undefined }[] = [];
  const dates: (string | null)[] = [];
  const forbidden: string[] = [];
  let operationReads = 0;
  await context.route('**/*', async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== 'http://127.0.0.1:8124') { forbidden.push(url.pathname); await route.abort(); return; }
    if (url.pathname === '/api/v1/ai-consent') {
      expect(request.method()).toBe('GET');
      await route.fulfill({ json: { state: 'REVOKED', revision: 1, policy: null, canRequestAi: false,
        acceptedPolicyVersion: null, acceptedPolicyDigest: null, lastChoiceAt: null } }); return;
    }
    if (url.pathname === '/api/v1/review-queue') {
      expect(request.method()).toBe('GET'); expect(url.searchParams.get('dueOnly')).toBe('true');
      dates.push(url.searchParams.get('noteDate')); await route.fulfill({ json: queue(cards) }); return;
    }
    if (url.pathname.startsWith('/api/v1/word-forms/')) {
      expect(request.method()).toBe('GET');
      const item = cards.find(item => url.pathname.endsWith(item.wordFormId));
      if (!item) { await failure(route, 'NOT_FOUND', undefined, 404); return; }
      await route.fulfill({ json: detail(item) }); return;
    }
    if (url.pathname === '/api/v1/cards/card_one/reviews') {
      expect(request.method()).toBe('POST');
      posts.push({ body: request.postData(), key: request.headers()['idempotency-key'], revision: request.headers()['if-match'] });
      await mutation(route); return;
    }
    if (url.pathname === '/api/v1/operations/op_synthetic') {
      operationReads += 1;
      await route.fulfill({ json: { operationId: 'op_synthetic', kind: 'REVIEW', status: operation,
        createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z',
        ...(operation === 'SUCCEEDED' ? { resultRef: 'event_synthetic' } : {}) } satisfies Operation }); return;
    }
    if (url.pathname.startsWith('/api/v1/') && request.method() !== 'GET') {
      forbidden.push(url.pathname); await route.abort(); return;
    }
    await route.continue();
  });
  return { posts, dates, forbidden, reads: () => operationReads,
    cards: (next: Card[]) => { cards = next; },
    submit: (handler: (route: Route) => Promise<void>) => { mutation = handler; },
    operation: (state: Operation['status']) => { operation = state; } };
}

test.describe('T033 review through the application shell', () => {
  for (const rating of ['AGAIN', 'HARD', 'GOOD', 'EASY'] as const) {
    test(`${rating} reveals by keyboard and advances only on a server receipt`, async ({ page, context }) => {
      const backend = await fixture(context);
      await page.goto('/review');
      await expect(page.getByRole('heading', { level: 1, name: 'Ôn tập flashcard' })).toBeVisible();
      await expect(page.getByText('vững chắc', { exact: true })).toHaveCount(0);
      const reveal = page.getByRole('button', { name: 'Lật thẻ', exact: true });
      await reveal.focus(); await reveal.press('Space');
      await expect(page.getByRole('button', { name: 'AGAIN', exact: true })).toBeFocused();
      await expect(page.getByText('A robust design.', { exact: true })).toBeVisible();
      const ratingButton = page.getByRole('button', { name: rating, exact: true });
      await ratingButton.focus(); await ratingButton.press('Enter');
      await expect(page.getByRole('heading', { level: 2, name: 'precise' })).toBeVisible();
      await expect(page.getByText('vững chắc', { exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Lật thẻ', exact: true })).toBeFocused();
      expect(backend.posts).toHaveLength(1); expect(backend.posts[0].revision).toBe('"7"');
      expect(backend.posts[0].key).toBeTruthy(); expect(JSON.parse(backend.posts[0].body!)).toEqual({ rating, source: 'FLASHCARD' });
      await expect(page.getByText('2026-10-22T17:00:00Z', { exact: true })).toBeVisible();
      expect(backend.forbidden).toEqual([]);
    });
  }

  test('loading, date filtering and empty queues use only server eligibility', async ({ page, context }) => {
    const backend = await fixture(context); backend.cards([]);
    await page.goto('/review?noteDate=2026-10-08');
    await expect(page.getByText('Không có thẻ đến hạn hoặc chưa học.', { exact: true })).toBeVisible();
    expect(backend.dates).toContain('2026-10-08');
    await page.getByRole('button', { name: 'Tất cả ngày', exact: true }).click();
    await expect(page.getByLabel('Ngày ghi chú', { exact: true })).toHaveValue('');
    await expect.poll(() => backend.dates.at(-1)).toBe(null);
    expect(backend.posts).toHaveLength(0); expect(backend.forbidden).toEqual([]);
  });

  test('pending controls block duplicate clicks and preserve the current card', async ({ page, context }) => {
    const backend = await fixture(context);
    let finish!: () => void;
    const held = new Promise<void>(resolve => { finish = resolve; });
    backend.submit(async route => { await held; backend.cards([card('two', 12)]); await route.fulfill({ status: 201, json: event('GOOD') }); });
    await page.goto('/review'); await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    await page.getByRole('button', { name: 'GOOD', exact: true }).click();
    await expect(page.getByRole('button', { name: 'GOOD', exact: true })).toBeDisabled();
    await expect(page.getByLabel('Ngày ghi chú', { exact: true })).toBeDisabled();
    await expect(page.getByRole('heading', { level: 2, name: 'robust' })).toBeVisible();
    expect(backend.posts).toHaveLength(1);
    finish(); await expect(page.getByRole('heading', { level: 2, name: 'precise' })).toBeVisible();
  });

  test('stale revisions require rereading before a fresh rating', async ({ page, context }) => {
    const backend = await fixture(context); backend.submit(route => failure(route, 'REVISION_CONFLICT', 'op_synthetic'));
    await page.goto('/review'); await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    await page.getByRole('button', { name: 'GOOD', exact: true }).click();
    await expect(page.locator('#review-status')).toContainText('Thẻ đã thay đổi');
    await expect(page.getByRole('button', { name: 'GOOD', exact: true })).toBeDisabled();
    backend.cards([card('one', 19)]); await page.getByRole('button', { name: 'Đọc lại hàng đợi', exact: true }).click();
    await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    await page.getByRole('button', { name: 'HARD', exact: true }).click();
    expect(backend.posts[1].revision).toBe('"19"'); expect(backend.posts[1].key).not.toBe(backend.posts[0].key);
  });

  test('a lost mutation response survives navigation and reload with identical-intent recovery', async ({ page, context }) => {
    const backend = await fixture(context); backend.submit(route => route.abort());
    await page.goto('/review'); await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    await page.getByRole('button', { name: 'EASY', exact: true }).click();
    await expect(page.locator('#review-status')).toContainText('Chưa xác định');
    const first = backend.posts[0];
    await page.getByRole('link', { name: 'Tìm kiếm', exact: true }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Tìm kiếm từ vựng' })).toBeVisible();
    await page.getByRole('link', { name: 'Ôn tập', exact: true }).click(); await page.reload();
    await expect(page.locator('#review-status')).toContainText('Chưa xác định');
    expect(backend.posts).toHaveLength(1);
    backend.submit(async route => { backend.cards([]); await route.fulfill({ status: 201, json: event('EASY') }); });
    await page.getByRole('button', { name: 'Kiểm tra kết quả', exact: true }).click();
    await expect(page.getByText('Không có thẻ đến hạn hoặc chưa học.', { exact: true })).toBeVisible();
    expect(backend.posts[1]).toEqual(first); expect(backend.forbidden).toEqual([]);
  });

  test('in-flight operations are read before same-key receipt replay', async ({ page, context }) => {
    const backend = await fixture(context); backend.submit(route => failure(route, 'IDEMPOTENCY_IN_FLIGHT', 'op_synthetic'));
    await page.goto('/review'); await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    await page.getByRole('button', { name: 'GOOD', exact: true }).click();
    await page.getByRole('button', { name: 'Kiểm tra kết quả', exact: true }).click();
    await expect(page.locator('#review-status')).toContainText('Biên nhận chưa hoàn tất');
    expect(backend.reads()).toBe(1); expect(backend.posts).toHaveLength(1);
    backend.operation('SUCCEEDED');
    backend.submit(async route => { backend.cards([]); await route.fulfill({ status: 201, json: event('GOOD') }); });
    await page.getByRole('button', { name: 'Kiểm tra kết quả', exact: true }).click();
    await expect(page.getByText('Không có thẻ đến hạn hoặc chưa học.', { exact: true })).toBeVisible();
    expect(backend.posts[1]).toEqual(backend.posts[0]); expect(backend.reads()).toBe(2);
  });

  test('reveal and rating reflow at supported widths with accessible status @a11y', async ({ page, context }) => {
    const backend = await fixture(context); await page.goto('/review');
    await page.getByRole('button', { name: 'Lật thẻ', exact: true }).click();
    for (const width of [320, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    }
    const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
    expect(scan.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
    expect(backend.posts).toHaveLength(0); expect(backend.forbidden).toEqual([]);
  });
});
