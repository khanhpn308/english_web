// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { SearchPage } from './SearchPage';
import { WordDetail } from './WordDetail';
import type { components } from '@/shared/api/generated';

type Page = components['schemas']['WordFormCollection'];
type Detail = components['schemas']['WordFormDetail'];
const summary = { id: 'form_synthetic', lemma: 'robust', partOfSpeech: 'ADJECTIVE', meaningViMatch: 'vững chắc', noteDates: ['2026-10-09'], revision: 1, updatedAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED' } satisfies Page['data'][number];
const page = (data: Page['data'] = [summary], nextCursor: string | null = null): Page => ({ data, pagination: { nextCursor, hasMore: nextCursor !== null, pageSize: 50 }, sort: { by: 'relevance', direction: 'ASC' } });
const detail: Detail = { ...summary, familyId: 'family_synthetic', meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'VERIFIED' }], meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }], examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }], ipaUs: null, cambridgeUrl: null, sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'VALID' }], card: null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const failure = (code: string, status = 503) => json({ error: { code, message: 'private backend exception', requestId: 'req_synthetic' } }, status);
let root: Root;
let host: HTMLDivElement;
let path: string;
let read: (url: string, init: RequestInit) => Promise<Response>;
let calls: { url: string; signal: AbortSignal | null | undefined }[];
async function render() { await act(async () => root.render(<SearchPage path={path} onNavigate={navigate} />)); }
function navigate(next: string) { path = next; window.history.replaceState(null, '', next); root.render(<SearchPage path={path} onNavigate={navigate} />); }
async function click(label: string) {
  const target = [...host.querySelectorAll('button')].find(button => button.textContent === label);
  if (!target) throw new Error(`Missing button ${label}`);
  await act(async () => target.click());
}
async function edit(id: string, value: string) {
  await act(async () => {
    const input = host.querySelector<HTMLInputElement>(`#${id}`)!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  path = '/search'; calls = []; read = async () => json(page());
  window.history.replaceState(null, '', '/');
  vi.stubGlobal('fetch', vi.fn((url: string, init: RequestInit) => { calls.push({ url, signal: init.signal }); return read(url, init); }));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); });

describe('T028 local search', () => {
  it('requires explicit browse and presents actual page data', async () => {
    await render(); expect(calls).toHaveLength(0);
    await click('Duyệt kho từ'); expect(host.textContent).toContain('robust'); expect(host.textContent).toContain('1 kết quả trên trang này');
  });
  it('restores all supported URL filters and sort', async () => {
    path = '/search?meaningVi=vững+chắc&lemma=robust&partOfSpeech=ADJECTIVE&verificationStatus=UNVERIFIED&sourceStatus=VALID&noteDate=2026-10-09&sortBy=lemma&sortOrder=DESC&pageSize=20';
    await render(); const query = new URL(calls[0].url, 'http://localhost').searchParams;
    expect(query.get('meaningVi')).toBe('vững chắc'); expect(query.get('pageSize')).toBe('20'); expect(query.get('sortOrder')).toBe('DESC');
    expect(Object.fromEntries(query)).toEqual({ meaningVi: 'vững chắc', lemma: 'robust', partOfSpeech: 'ADJECTIVE', verificationStatus: 'UNVERIFIED', sourceStatus: 'VALID', noteDate: '2026-10-09', sortBy: 'lemma', sortOrder: 'DESC', pageSize: '20' });
    expect(host.querySelector<HTMLInputElement>('#meaningVi')!.value).toBe('vững chắc');
  });
  it('preserves literal question marks in URL query values', async () => {
    path = '/search?meaningVi=a?b&sourceStatus=VALID'; await render();
    const query = new URL(calls[0].url, 'http://localhost').searchParams;
    expect(query.get('meaningVi')).toBe('a?b'); expect(query.get('sourceStatus')).toBe('VALID');
  });
  it('distinguishes an empty match from a stopped local API and preserves intent on retry', async () => {
    path = '/search?lemma=robust'; read = async () => json(page([])); await render();
    expect(host.textContent).toContain('Không tìm thấy');
    read = async () => { throw new TypeError('private backend exception'); };
    await click('Tìm kiếm'); expect(host.textContent).toContain('Cannot Reach Server'); expect(host.textContent).not.toContain('Không tìm thấy');
    read = async () => json(page()); await click('Retry Action'); expect(host.textContent).toContain('robust'); expect(path).toContain('lemma=robust');
  });
  it('aborts obsolete requests and suppresses reverse-order resolved responses', async () => {
    path = '/search?lemma=old'; let resolveOld!: (value: Response) => void;
    read = url => url.includes('lemma=old') ? new Promise(resolve => { resolveOld = resolve; }) : Promise.resolve(json(page([{ ...summary, lemma: 'new' }])));
    await render(); expect(host.textContent).toContain('Đang tải'); await edit('lemma', 'new');
    expect(calls[0].signal?.aborted).toBe(true); expect(host.textContent).toContain('new');
    await act(async () => resolveOld(json(page([{ ...summary, lemma: 'stale' }]))));
    expect(host.textContent).not.toContain('stale');
  });
  it('pages using the opaque server cursor and restarts expiry without losing filters', async () => {
    path = '/search?lemma=robust'; read = async url => url.includes('cursor=') ? failure('CURSOR_EXPIRED', 409) : json(page([summary], 'opaque_cursor'));
    await render(); await click('Trang tiếp');
    expect(path).not.toContain('cursor='); expect(path).toContain('lemma=robust'); expect(host.textContent).toContain('Trang đã hết hạn');
    expect(calls).toHaveLength(3);
  });
  it('shows a successful next page and resets the cursor when filters change', async () => {
    path = '/search?lemma=robust'; read = async url => json(url.includes('cursor=') ? page([{ ...summary, id: 'form_next', lemma: 'resilient' }]) : page([summary], 'opaque_cursor'));
    await render(); await click('Trang tiếp'); expect(host.textContent).toContain('resilient'); expect(path).toContain('cursor=opaque_cursor');
    await edit('meaningVi', 'bền'); expect(path).not.toContain('cursor='); expect(path).toContain('meaningVi=');
  });
  it('does not reuse old A data or accept B after returning A -> B -> A', async () => {
    path = '/search?lemma=A'; await render();
    let resolveB!: (value: Response) => void;
    let resolveA!: (value: Response) => void;
    read = url => new Promise(resolve => { if (url.includes('lemma=B')) resolveB = resolve; else resolveA = resolve; });
    await edit('lemma', 'B'); await edit('lemma', 'A');
    expect(host.textContent).toContain('Đang tải'); expect(host.querySelector('ul')).toBeNull();
    await act(async () => resolveB(json(page([{ ...summary, lemma: 'stale B' }]))));
    expect(host.textContent).not.toContain('stale B');
    await act(async () => resolveA(json(page([{ ...summary, lemma: 'fresh A' }]))));
    expect(host.textContent).toContain('fresh A');
  });
  it('suppresses both obsolete A and B responses after the newest A resolves', async () => {
    path = '/search?lemma=A';
    const pending: ((value: Response) => void)[] = [];
    read = () => new Promise(resolve => pending.push(resolve));
    await render(); await edit('lemma', 'B'); await edit('lemma', 'A');
    expect(calls[0].signal?.aborted).toBe(true); expect(calls[1].signal?.aborted).toBe(true);
    await act(async () => pending[2](json(page([{ ...summary, lemma: 'newest A' }]))));
    await act(async () => { pending[1](json(page([{ ...summary, lemma: 'stale B' }]))); pending[0](json(page([{ ...summary, lemma: 'stale A' }]))); });
    expect(host.textContent).toContain('newest A'); expect(host.textContent).not.toContain('stale');
  });
  it('withholds unsafe correlation IDs', async () => {
    path = '/search?lemma=robust'; read = async () => json({ error: { code: 'STORAGE_UNAVAILABLE', message: 'private backend exception', requestId: '/private/internal/path' } }, 503);
    await render(); expect(host.textContent).not.toContain('/private/internal/path');
  });
  it('uses fixed recovery copy for error codes matching object prototype keys', async () => {
    path = '/search?lemma=robust'; read = async () => failure('constructor'); await render();
    expect(host.querySelector('[role="alert"]')).not.toBeNull();
    expect(host.textContent).toContain('Không đọc được dữ liệu');
    expect(host.textContent).not.toContain('function Object'); expect(host.textContent).not.toContain('private backend exception');
  });
  it('recovers safely when an error envelope contains an object instead of a code string', async () => {
    path = '/search?lemma=robust';
    read = async () => json({ error: { code: { toString: null }, message: 'private backend exception', requestId: 'req_synthetic' } }, 503);
    await render(); expect(host.querySelector('[role="alert"]')).not.toBeNull();
    expect(host.textContent).not.toContain('private backend exception'); expect(host.textContent).not.toContain('Đang tải');
    read = async () => json(page()); await click('Retry Action');
    expect(host.querySelector('ul[aria-label="Kết quả tìm kiếm"]')?.textContent).toContain('robust');
  });
  it('reports an invalid non-JSON success response instead of loading forever', async () => {
    path = '/search?lemma=robust'; read = async () => new Response('unexpected response', { headers: { 'Content-Type': 'text/html' } });
    await render(); expect(host.querySelector('[role="alert"]')).not.toBeNull(); expect(host.textContent).not.toContain('Đang tải');
  });
  it.each([false, 0, '', {}, { data: null }, { ...page(), pagination: null }, { ...page(), data: [{ ...summary, noteDates: null }] }])('recovers from malformed JSON search success %# without loading forever or rendering a result', async body => {
    path = '/search?lemma=robust'; read = async () => json(body); await render();
    expect(host.querySelector('[role="alert"]')).not.toBeNull();
    expect(host.textContent).not.toContain('Đang tải');
    expect(host.querySelector('ul[aria-label="Kết quả tìm kiếm"]')).toBeNull();
    read = async () => json(page()); await click('Retry Action');
    expect(host.querySelector('ul[aria-label="Kết quả tìm kiếm"]')?.textContent).toContain('robust');
    expect(path).toBe('/search?lemma=robust');
  });
  it.each(['STORAGE_UNAVAILABLE', 'SESSION_INVALID', 'INVALID_QUERY', 'SOURCE_INVALID', 'INTERNAL_ERROR'])('keeps %s distinct and hides private errors', async code => {
    path = '/search?lemma=robust'; read = async () => failure(code); await render();
    expect(host.querySelector('[role="alert"]')).not.toBeNull(); expect(host.textContent).not.toContain('private backend exception'); expect(host.textContent).not.toContain('Không tìm thấy');
  });
  it('aborts reads on route unmount', async () => {
    path = '/search?lemma=robust'; read = () => new Promise(() => {}); await render();
    await act(async () => root.render(<p>Other route</p>)); expect(calls[0].signal?.aborted).toBe(true);
  });
});

describe('T028 detail', () => {
  async function mount() { await act(async () => root.render(<WordDetail wordFormId="form_synthetic" path="/word-forms/form_synthetic?returnTo=%2Fsearch%3Flemma%3Drobust" onNavigate={vi.fn()} />)); }
  it('shows verification, meanings, examples and real source dates', async () => {
    read = async () => json(detail); await mount();
    expect(host.textContent).toContain('2026-10-09'); expect(host.textContent).toContain('Chưa xác minh'); expect(host.textContent).toContain('Nguồn hợp lệ'); expect(host.textContent).toContain('Một thiết kế vững chắc.');
    expect(host.querySelector('a')!.getAttribute('href')).toBe('/search?lemma=robust');
  });
  it.each(['INVALID', 'MISSING'] as const)('makes %s sources explicit and withholds current study text', async status => {
    // Retain stale content to prove that the UI itself withholds it.
    read = async () => json({ ...detail, sourceRefs: [{ ...detail.sourceRefs[0], status }], verificationSummary: 'MISSING' } satisfies Detail);
    await mount(); expect(host.textContent).toContain('Không có nguồn hợp lệ'); expect(host.textContent).not.toContain('Một thiết kế vững chắc.');
    expect(host.querySelector('#meaning-heading')).toBeNull(); expect(host.querySelector('#example-heading')).toBeNull();
  });
  it('keeps current content when another source remains valid and identifies both source states', async () => {
    read = async () => json({ ...detail, sourceRefs: [...detail.sourceRefs, { sourceId: 'source_invalid', noteDate: '2026-10-08', status: 'INVALID' }] } satisfies Detail);
    await mount(); expect(host.textContent).toContain('Nguồn hợp lệ'); expect(host.textContent).toContain('Nguồn không hợp lệ');
    expect(host.textContent).toContain('Một thiết kế vững chắc.'); expect(host.textContent).not.toContain('Không có nguồn hợp lệ');
  });
  it('explains absent source links and withholds current content', async () => {
    read = async () => json({ ...detail, sourceRefs: [] } satisfies Detail); await mount();
    expect(host.textContent).toContain('Không có nguồn hợp lệ'); expect(host.textContent).toContain('Không có nguồn được liên kết');
    expect(host.querySelector('#meaning-heading')).toBeNull();
  });
  it('presents missing forms safely', async () => {
    read = async () => failure('NOT_FOUND', 404); await mount(); expect(host.textContent).toContain('Không tìm thấy dạng từ'); expect(host.textContent).not.toContain('private backend exception');
  });
  it.each([false, 0, '', {}, { ...detail, sourceRefs: null }, { ...detail, meaningsVi: [null] }, { ...detail, examples: [{ english: {} }] }, { ...detail, card: {} }])('recovers from malformed JSON detail success %# without a render error', async body => {
    read = async () => json(body); await mount();
    expect(host.querySelector('[role="alert"]')).not.toBeNull();
    expect(host.textContent).not.toContain('Đang tải');
    expect(host.textContent).not.toContain('Một thiết kế vững chắc.');
    expect(host.querySelector('a')!.getAttribute('href')).toBe('/search?lemma=robust');
    read = async () => json(detail); await click('Retry Action');
    expect(host.textContent).toContain('Một thiết kế vững chắc.');
  });
  it('rejects a malformed encoded ID without issuing a request', async () => {
    await act(async () => root.render(<WordDetail wordFormId="%invalid" path="/word-forms/%invalid" onNavigate={vi.fn()} />));
    expect(calls).toHaveLength(0); expect(host.textContent).toContain('Địa chỉ dạng từ không hợp lệ');
  });
  it('ignores unsafe return destinations and stored dictionary URLs', async () => {
    read = async () => json({ ...detail, cambridgeUrl: 'javascript:alert(1)' } satisfies Detail);
    await act(async () => root.render(<WordDetail wordFormId="form_synthetic" path="/word-forms/form_synthetic?returnTo=https%3A%2F%2Fexample.invalid" onNavigate={vi.fn()} />));
    expect(host.querySelector('a')!.getAttribute('href')).toBe('/search'); expect(host.textContent).toContain('Liên kết từ điển không hợp lệ');
    expect(host.querySelector('[href^="javascript:"]')).toBeNull();
  });
  it('renders stored text as text and allows only the validated dictionary link', async () => {
    const storedText = '<img src=x onerror=alert(1)>';
    read = async () => json({ ...detail, lemma: storedText, meaningsVi: [{ text: storedText, language: 'vi', verificationStatus: 'MISSING' }], cambridgeUrl: 'https://dictionary.cambridge.org/dictionary/english/robust' } satisfies Detail);
    await mount(); expect(host.textContent).toContain(storedText); expect(host.querySelector('img')).toBeNull();
    expect(host.querySelector('a[href^="https://dictionary.cambridge.org/"]')?.textContent).toBe('Từ điển Cambridge');
  });
});
