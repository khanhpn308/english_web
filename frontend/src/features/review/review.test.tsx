// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/shared/api/generated';
import { AppShell } from '@/app/AppShell';
import { ReviewPage } from './ReviewPage';

type Card = components['schemas']['ReviewCardView'];
type Queue = components['schemas']['ReviewQueueView'];
type Detail = components['schemas']['WordFormDetail'];
type ReviewEvent = components['schemas']['ReviewEventView'];
const card = (id = 'one', revision = 7): Card => ({ cardId: `card_${id}`, wordFormId: `form_${id}`,
  lemma: id === 'one' ? 'robust' : 'precise', queueRevision: revision, state: 'NEW',
  dueAt: null, noteDates: ['2026-10-09'] });
const queue = (cards = [card()]): Queue => ({ data: cards,
  pagination: { pageSize: 50, hasMore: false, nextCursor: null }, sort: { by: 'dueAt', direction: 'ASC' } });
const detail = (item = card()): Detail => ({ id: item.wordFormId, familyId: 'family_synthetic',
  lemma: item.lemma, partOfSpeech: 'ADJECTIVE', revision: 1, updatedAt: '2026-10-09T00:00:00Z',
  ipaUs: '/roʊˈbʌst/', cambridgeUrl: null, verificationSummary: 'UNVERIFIED',
  meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'UNVERIFIED' }],
  meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
  examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
  sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'VALID' }],
  card: { id: item.cardId, state: item.state, dueAt: item.dueAt } });
const event = (rating: ReviewEvent['rating'] = 'GOOD'): ReviewEvent => ({ id: 'event_synthetic',
  cardId: 'card_one', rating, source: 'FLASHCARD', operationId: 'op_synthetic',
  reviewedAt: '2026-10-09T00:00:00Z', nextDueAt: '2026-10-22T17:00:00Z' });
function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
}
function failure(code: string, status = 409, operationId?: string) {
  return response({ error: { code, message: 'Synthetic failure', requestId: 'req_synthetic',
    ...(operationId ? { details: { kind: 'RETRY', operationId } } : {}) } }, status);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
let root: Root;
let container: HTMLDivElement;
let requests: { url: string; init: RequestInit }[];
let readQueue: (url: string) => Promise<Response>;
let readDetail: (url: string) => Promise<Response>;
let submit: (init: RequestInit) => Promise<Response>;
let operation: () => Promise<Response>;
const posts = () => requests.filter(item => item.init.method === 'POST');
function button(label: string) {
  const result = [...container.querySelectorAll('button')].find(item => item.textContent === label);
  if (!result) throw new Error(`Missing button ${label}`);
  return result;
}
async function click(label: string) { await act(async () => button(label).click()); }
async function mount(active = true) { await act(async () => root.render(<ReviewPage active={active} />)); }
async function editDate(value: string) {
  await act(async () => {
    const input = container.querySelector<HTMLInputElement>('#review-note-date')!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  window.sessionStorage.clear(); window.history.replaceState(null, '', '/review');
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  requests = [];
  readQueue = async () => response(queue()); readDetail = async () => response(detail());
  submit = async init => { readQueue = async () => response(queue([card('two', 12)]));
    readDetail = async () => response(detail(card('two', 12)));
    return response(event(JSON.parse(String(init.body)).rating), 201); };
  operation = async () => response({ operationId: 'op_synthetic', kind: 'REVIEW', status: 'UNKNOWN',
    createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    requests.push({ url, init });
    if (url.startsWith('/api/v1/review-queue')) return readQueue(url);
    if (url.startsWith('/api/v1/word-forms/')) return readDetail(url);
    if (url.startsWith('/api/v1/cards/')) return submit(init);
    if (url.startsWith('/api/v1/operations/')) return operation();
    if (url === '/api/v1/ai-consent') return response({ state: 'REVOKED', revision: 1, policy: null,
      canRequestAi: false, acceptedPolicyVersion: null, acceptedPolicyDigest: null, lastChoiceAt: null });
    throw new Error(`Unexpected request ${url}`);
  }));
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  vi.useRealTimers();
  window.sessionStorage.clear();
});

describe('T033 server-authoritative flashcard review', () => {
  it('announces loading and an empty due/new queue without inventing a total', async () => {
    const held = deferred<Response>(); readQueue = () => held.promise;
    await mount(); expect(container.textContent).toContain('Đang tải hàng đợi');
    await act(async () => held.resolve(response(queue([]))));
    expect(container.textContent).toContain('Không có thẻ đến hạn hoặc chưa học');
    expect(container.querySelector('[data-flashcard]')).toBeNull(); expect(posts()).toHaveLength(0);
  });
  it('uses the supported noteDate filter and server dueOnly=true', async () => {
    await mount(); await editDate('2026-10-08');
    const reads = requests.filter(item => item.url.startsWith('/api/v1/review-queue'));
    expect(new URL(reads.at(-1)!.url, 'http://localhost').searchParams.get('noteDate')).toBe('2026-10-08');
    expect(requests.filter(item => item.url.startsWith('/api/v1/review-queue'))
      .every(item => new URL(item.url, 'http://localhost').searchParams.get('dueOnly') === 'true')).toBe(true);
    expect(window.location.search).toContain('noteDate=2026-10-08');
  });
  it('keeps all meaning and example content out of the DOM before reveal', async () => {
    await mount(); expect(container.textContent).toContain('robust');
    expect(container.textContent).not.toContain('vững chắc');
    expect(container.textContent).not.toContain('A robust design.');
    expect(container.querySelector('[aria-label="Đánh giá thẻ"]')).toBeNull();
    await click('Lật thẻ');
    for (const text of ['vững chắc', 'strong', 'A robust design.', 'Một thiết kế vững chắc.', 'UNVERIFIED']) {
      expect(container.textContent).toContain(text);
    }
    expect(document.activeElement).toBe(button('AGAIN'));
  });
  it.each(['AGAIN', 'HARD', 'GOOD', 'EASY'] as const)('sends %s with the individual card revision and advances after server confirmation', async rating => {
    const invalidation = vi.fn(); window.addEventListener('vocabulary:invalidate', invalidation);
    try {
      await mount(); await click('Lật thẻ'); await click(rating);
      const request = posts()[0]; const headers = new Headers(request.init.headers);
      expect(request.url).toBe('/api/v1/cards/card_one/reviews');
      expect(headers.get('If-Match')).toBe('"7"'); expect(headers.get('Idempotency-Key')).toBeTruthy();
      expect(request.init.credentials).toBe('same-origin');
      expect(JSON.parse(String(request.init.body))).toEqual({ rating, source: 'FLASHCARD' });
      expect(container.textContent).toContain('precise'); expect(container.textContent).toContain(event(rating).nextDueAt);
      expect(container.textContent).not.toContain('vững chắc'); expect(invalidation).toHaveBeenCalledOnce();
    } finally { window.removeEventListener('vocabulary:invalidate', invalidation); }
  });

  it('keeps the card and prevents same-tick duplicate ratings while awaiting confirmation', async () => {
    const held = deferred<Response>(); submit = () => held.promise;
    await mount(); await click('Lật thẻ');
    await act(async () => { button('GOOD').click(); button('EASY').click(); });
    expect(posts()).toHaveLength(1); expect(container.textContent).toContain('robust');
    expect(button('GOOD').disabled).toBe(true);
    expect(container.textContent).not.toContain('Đã ghi nhận đánh giá');
    readQueue = async () => response(queue([card('two', 12)]));
    readDetail = async () => response(detail(card('two', 12)));
    await act(async () => held.resolve(response(event(), 201)));
    expect(container.textContent).toContain('precise');
    expect(container.textContent).not.toContain('vững chắc');
    expect(button('Lật thẻ').disabled).toBe(false);
  });

  it('requires an explicit reread after a stale revision and uses the newly returned per-card revision', async () => {
    submit = async () => failure('REVISION_CONFLICT', 409, 'op_synthetic');
    await mount(); await click('Lật thẻ'); await click('GOOD');
    expect(container.textContent).toContain('robust'); expect(button('GOOD').disabled).toBe(true);
    expect(container.textContent).toContain('REVISION_CONFLICT');
    readQueue = async () => response(queue([card('one', 19)]));
    await click('Đọc lại hàng đợi'); await click('Lật thẻ'); await click('HARD');
    expect(new Headers(posts()[1].init.headers).get('If-Match')).toBe('"19"');
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key'))
      .not.toBe(new Headers(posts()[0].init.headers).get('Idempotency-Key'));
  });

  it('replays a lost response with the identical key, rating and revision, never advancing from a queue guess', async () => {
    submit = async () => { throw new TypeError('Synthetic offline'); };
    await mount(); await click('Lật thẻ'); await click('EASY');
    const first = posts()[0]; expect(container.textContent).toContain('Chưa xác định');
    await editDate('2026-10-08'); expect(window.location.search).toBe('');
    submit = async () => response(event('EASY'), 201);
    readQueue = async () => response(queue([]));
    await click('Kiểm tra kết quả');
    expect(posts()[1].init.body).toBe(first.init.body);
    for (const name of ['If-Match', 'Idempotency-Key']) {
      expect(new Headers(posts()[1].init.headers).get(name)).toBe(new Headers(first.init.headers).get(name));
    }
    expect(container.textContent).toContain('Đã ghi nhận đánh giá EASY');
  });

  it.each(['PENDING', 'UNKNOWN'] as const)('reads a %s operation without resubmitting or allowing a fresh intent', async state => {
    submit = async () => failure('IDEMPOTENCY_IN_FLIGHT', 409, 'op_synthetic');
    operation = async () => response({ operationId: 'op_synthetic', kind: 'REVIEW', status: state,
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await mount(); await click('Lật thẻ'); await click('AGAIN'); await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(1); expect(button('GOOD').disabled).toBe(true);
    expect(requests.some(item => item.url === '/api/v1/operations/op_synthetic')).toBe(true);
    expect(container.textContent).not.toContain('Đã ghi nhận đánh giá');
  });

  it('retrieves the receipt with the same key after an operation succeeds', async () => {
    submit = async () => failure('STORAGE_BUSY', 503, 'op_synthetic');
    await mount(); await click('Lật thẻ'); await click('GOOD');
    operation = async () => response({ operationId: 'op_synthetic', kind: 'REVIEW', status: 'SUCCEEDED',
      resultRef: 'event_synthetic', createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    submit = async () => response(event(), 201); readQueue = async () => response(queue([]));
    await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(2);
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key'))
      .toBe(new Headers(posts()[0].init.headers).get('Idempotency-Key'));
    expect(container.textContent).toContain('Đã ghi nhận đánh giá GOOD');
  });

  it('settles a failed operation without replay and preserves the card for an explicit reread', async () => {
    submit = async () => failure('STORAGE_BUSY', 503, 'op_synthetic');
    operation = async () => response({ operationId: 'op_synthetic', kind: 'REVIEW', status: 'FAILED',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await mount(); await click('Lật thẻ'); await click('GOOD'); await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(1); expect(container.textContent).toContain('đã thất bại');
    expect(container.textContent).toContain('robust'); expect(button('GOOD').disabled).toBe(true);
  });

  it.each(['VALIDATION_ERROR', 'SESSION_INVALID', 'ORIGIN_FORBIDDEN', 'IDEMPOTENCY_KEY_REUSED'])(
    'preserves the card and reports %s without false success', async code => {
      submit = async () => failure(code, code === 'SESSION_INVALID' ? 401 : 422);
      await mount(); await click('Lật thẻ'); await click('GOOD');
      expect(container.textContent).toContain(code); expect(container.textContent).toContain('robust');
      expect(container.textContent).not.toContain('Đã ghi nhận đánh giá');
      expect(container.textContent).not.toContain('Synthetic failure'); expect(button('GOOD').disabled).toBe(true);
    });

  it.each([response(null, 201), response({ ...event(), cardId: 'other' }, 201),
    new Response('{broken', { status: 201, headers: { 'Content-Type': 'application/json' } })])(
    'retains the original intent when a success response is unusable', async value => {
      submit = async () => value;
      await mount(); await click('Lật thẻ'); await click('GOOD');
      expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
      expect(container.textContent).not.toContain('Đã ghi nhận đánh giá');
    });

  it('ignores obsolete queue and detail responses after the date filter changes', async () => {
    const oldQueue = deferred<Response>(); let reads = 0;
    readQueue = () => ++reads === 1 ? oldQueue.promise : Promise.resolve(response(queue([card('two', 12)])));
    readDetail = async () => response(detail(card('two', 12)));
    await mount(); await editDate('2026-10-08');
    await act(async () => oldQueue.resolve(response(queue())));
    expect(container.textContent).toContain('precise'); expect(container.textContent).not.toContain('robust');
    const oldDetail = deferred<Response>(); readQueue = async () => response(queue()); readDetail = () => oldDetail.promise;
    await editDate('2026-10-07');
    readQueue = async () => response(queue([card('two', 12)])); readDetail = async () => response(detail(card('two', 12)));
    await editDate('2026-10-06');
    await act(async () => oldDetail.resolve(response(detail())));
    expect(button('Lật thẻ').disabled).toBe(false);
    await click('Lật thẻ'); expect(container.textContent).toContain('precise');
    expect(container.textContent).toContain('A robust design.');
  });

  it('shows invalid queue, mismatched details and invalid sources as errors with rating disabled', async () => {
    readQueue = async () => response({ invalid: true }); await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    readQueue = async () => response(queue()); readDetail = async () => response(detail(card('two')));
    await click('Thử lại'); expect(button('Lật thẻ').disabled).toBe(true);
    readDetail = async () => response({ ...detail(), sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'INVALID' }] });
    await click('Thử lại'); expect(container.textContent).toContain('nguồn hợp lệ');
    expect(button('Lật thẻ').disabled).toBe(true);
  });

  it('keeps the confirmed event when queue refresh fails and never posts it again', async () => {
    submit = async () => response(event(), 201);
    await mount(); await click('Lật thẻ'); readQueue = async () => { throw new TypeError('Synthetic offline'); };
    await click('GOOD'); expect(container.textContent).toContain('Đã ghi nhận đánh giá GOOD');
    expect(container.textContent).toContain('robust'); expect(button('GOOD').disabled).toBe(true);
    readQueue = async () => response(queue([])); await click('Thử lại'); expect(posts()).toHaveLength(1);
  });

  it('preserves unknown intent across leaving the route and component remount', async () => {
    submit = async () => { throw new TypeError('Synthetic offline'); };
    await mount(); await click('Lật thẻ'); await click('HARD'); const first = posts()[0];
    await mount(false); await mount(); expect(posts()).toHaveLength(1);
    await act(async () => root.unmount()); root = createRoot(container); await mount();
    expect(container.textContent).toContain('HARD'); expect(container.textContent).toContain('Chưa xác định');
    submit = async () => response(event('HARD'), 201); readQueue = async () => response(queue([]));
    await click('Kiểm tra kết quả');
    expect(posts()[1].init.body).toBe(first.init.body);
    expect(new Headers(posts()[1].init.headers).get('If-Match')).toBe('"7"');
  });

  it('aborts reads on navigation and ignores their late result without stealing focus', async () => {
    const held = deferred<Response>(); readQueue = () => held.promise; await mount();
    const signal = requests[0].init.signal; const link = document.createElement('button');
    document.body.append(link); link.focus(); await mount(false);
    expect(signal?.aborted).toBe(true);
    await act(async () => held.resolve(response(queue())));
    expect(container.querySelector('[data-flashcard]')).toBeNull(); expect(document.activeElement).toBe(link); link.remove();
  });

  it('renders the real shell review route while preserving search navigation', async () => {
    await act(async () => root.render(<AppShell currentPath="/review" />));
    expect(container.querySelector('a[href="/review"]')?.getAttribute('aria-current')).toBe('page');
    expect(container.querySelector('a[href="/search"]')).not.toBeNull();
    expect(container.textContent).toContain('robust');
    expect(container.querySelector('[aria-label="Thông báo trạng thái tính năng"]')).toBeNull();
  });

  it('uses the current URL after recovering a filtered intent retained through navigation', async () => {
    window.history.replaceState(null, '', '/review?noteDate=2026-10-08');
    submit = async () => { throw new TypeError('Synthetic offline'); };
    await mount(); await click('Lật thẻ'); await click('GOOD');
    await mount(false); window.history.pushState(null, '', '/review'); await mount();
    expect(container.querySelector<HTMLInputElement>('#review-note-date')!.value).toBe('2026-10-08');
    submit = async () => response(event(), 201); readQueue = async () => response(queue([]));
    await click('Kiểm tra kết quả');
    expect(container.querySelector<HTMLInputElement>('#review-note-date')!.value).toBe('');
    const reads = requests.filter(item => item.url.startsWith('/api/v1/review-queue'));
    expect(new URL(reads.at(-1)!.url, 'http://localhost').searchParams.has('noteDate')).toBe(false);
    expect(posts()[1].init.body).toBe(posts()[0].init.body);
  });

  it('restores the URL date on route activation and browser back navigation', async () => {
    await mount(); await editDate('2026-10-08'); await mount(false);
    window.history.pushState(null, '', '/review'); await mount();
    expect(container.querySelector<HTMLInputElement>('#review-note-date')!.value).toBe('');
    window.history.replaceState(null, '', '/review?noteDate=2026-10-07');
    await act(async () => window.dispatchEvent(new PopStateEvent('popstate')));
    expect(container.querySelector<HTMLInputElement>('#review-note-date')!.value).toBe('2026-10-07');
  });

  it('ignores a late operation success after leaving and returning to the route', async () => {
    submit = async () => failure('IDEMPOTENCY_IN_FLIGHT', 409, 'op_synthetic');
    await mount(); await click('Lật thẻ'); await click('GOOD');
    const held = deferred<Response>(); operation = () => held.promise;
    await click('Kiểm tra kết quả');
    const read = requests.find(item => item.url === '/api/v1/operations/op_synthetic')!;
    await mount(false); await mount(); expect(read.init.signal?.aborted).toBe(true);
    await act(async () => held.resolve(response({ operationId: 'op_synthetic', kind: 'REVIEW', status: 'SUCCEEDED',
      resultRef: 'event_synthetic', createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' })));
    expect(posts()).toHaveLength(1); expect(container.textContent).toContain('Chưa xác định');
    expect(button('GOOD').disabled).toBe(true);
  });

  it('an old unmounted mutation cannot erase a newer card intent persisted by the new mount', async () => {
    const original = deferred<Response>(); submit = () => original.promise;
    await mount(); await click('Lật thẻ'); await click('GOOD');
    await act(async () => root.unmount()); root = createRoot(container); await mount();
    submit = async () => response(event(), 201);
    readQueue = async () => response(queue([card('two', 12)])); readDetail = async () => response(detail(card('two', 12)));
    await click('Kiểm tra kết quả');
    submit = async () => { throw new TypeError('Synthetic offline'); };
    await click('Lật thẻ'); await click('HARD');
    const newer = window.sessionStorage.getItem('vocabulary.review.pending.v1');
    await act(async () => original.resolve(response(event(), 201)));
    expect(window.sessionStorage.getItem('vocabulary.review.pending.v1')).toBe(newer);
    expect(container.textContent).toContain('HARD'); expect(container.textContent).toContain('Chưa xác định');
  });

  it('keeps an ambiguous intent when an explicit replay encounters session expiry', async () => {
    submit = async () => { throw new TypeError('Synthetic offline'); };
    await mount(); await click('Lật thẻ'); await click('GOOD');
    submit = async () => failure('SESSION_INVALID', 401); await click('Kiểm tra kết quả');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).toContain('SESSION_INVALID');
    expect(button('GOOD').disabled).toBe(true);
    expect(window.sessionStorage.getItem('vocabulary.review.pending.v1')).not.toBeNull();
  });

  it('preserves intent at a mutation timeout and supports explicit same-key recovery', async () => {
    vi.useFakeTimers();
    submit = init => new Promise((_resolve, reject) => init.signal?.addEventListener('abort',
      () => reject(new DOMException('Synthetic timeout', 'AbortError')), { once: true }));
    await mount(); await click('Lật thẻ'); await click('GOOD');
    await act(async () => vi.advanceTimersByTimeAsync(15_000));
    expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
    submit = async () => response(event(), 201); readQueue = async () => response(queue([]));
    await click('Kiểm tra kết quả');
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key'))
      .toBe(new Headers(posts()[0].init.headers).get('Idempotency-Key'));
  });

  it('blocks rating without dispatch if browser storage cannot retain the intent', async () => {
    await mount(); await click('Lật thẻ');
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Synthetic full storage', 'QuotaExceededError'); });
    await click('GOOD'); expect(posts()).toHaveLength(0);
    expect(container.textContent).toContain('Chưa gửi yêu cầu'); expect(button('GOOD').disabled).toBe(true);
  });

  it('renders server due timestamps and partial-page information without deriving schedules or totals', async () => {
    const learned: Card = { ...card(), state: 'LEARNED', dueAt: '2020-02-01T17:00:00Z' };
    readQueue = async () => response({ ...queue([learned]), pagination: { pageSize: 1, hasMore: true, nextCursor: 'opaque_cursor' } });
    readDetail = async () => response(detail(learned));
    await mount(); expect(container.textContent).toContain('2020-02-01T17:00:00Z');
    expect(container.textContent).toContain('1 thẻ, còn trang tiếp theo');
    await click('Lật thẻ'); await click('GOOD');
    expect(JSON.parse(String(posts()[0].init.body))).toEqual({ rating: 'GOOD', source: 'FLASHCARD' });
    expect(container.textContent).toContain('2026-10-22T17:00:00Z');
  });

  it.each(['https://evil.invalid/dictionary/english/robust', 'javascript:alert(1)',
    'https://synthetic:fixture@dictionary.cambridge.org/dictionary/english/robust'])(
    'renders untrusted learning text literally and refuses unsafe dictionary links', async url => {
      readDetail = async () => response({ ...detail(), cambridgeUrl: url,
        meaningsVi: [{ text: '<script>synthetic()</script>', language: 'vi', verificationStatus: 'UNVERIFIED' }] });
      await mount(); await click('Lật thẻ');
      expect(container.textContent).toContain('<script>synthetic()</script>');
      expect(container.querySelector('script')).toBeNull();
      expect(container.querySelector('a[target="_blank"]')).toBeNull();
    });

  it('links only the approved Cambridge origin after reveal', async () => {
    const url = 'https://dictionary.cambridge.org/dictionary/english/robust';
    readDetail = async () => response({ ...detail(), cambridgeUrl: url }); await mount();
    expect(container.querySelector('a[target="_blank"]')).toBeNull(); await click('Lật thẻ');
    const link = container.querySelector<HTMLAnchorElement>('a[target="_blank"]')!;
    expect(link.href).toBe(url); expect(link.rel).toBe('noopener noreferrer'); expect(link.referrerPolicy).toBe('no-referrer');
  });
});
