// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/shared/api/generated';
import { AiConsentProvider } from '@/features/consent/AiConsentGate';
import { AiConsentPanel } from '@/features/consent/AiConsentPanel';
import { AppShell } from '@/app/AppShell';
import { LookupPage } from './LookupPage';

type View = components['schemas']['AiConsentView'];
type Preview = components['schemas']['LookupResult'];
const policy: NonNullable<View['policy']> = {
  version: 'synthetic-policy-v1', digest: 'a'.repeat(64), reviewStatus: 'READY',
  disclosureText: 'Synthetic disclosure', recipients: ['Synthetic recipient'],
  dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'],
  retentionStatement: 'Synthetic retention', regionStatement: 'Synthetic region',
  costQuotaStatement: 'Synthetic quota', withdrawalStatement: 'Synthetic withdrawal',
  scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [],
  dispatchRules: (['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'] as const).map(scope => ({
    scope, providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high',
    route: 'primary', billingMode: 'configured-account',
  })),
};
function view(state: View['state'] = 'GRANTED', revision = 1): View {
  return { state, revision, policy, canRequestAi: state === 'GRANTED',
    acceptedPolicyVersion: state === 'GRANTED' ? policy.version : null,
    acceptedPolicyDigest: state === 'GRANTED' ? policy.digest : null,
    lastChoiceAt: revision ? '2026-10-09T00:00:00Z' : null };
}
function preview(): Preview {
  return { lookupId: 'lookup_synthetic', operationId: 'op_synthetic', term: 'robust',
    provider: 'Antigravity/Google', model: 'gemini-3.8-flash-high', promptVersion: 'lookup-v1',
    status: 'PREVIEW', createdAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED',
    forms: [{ formId: 'draft_synthetic', lemma: 'robust', partOfSpeech: 'ADJECTIVE',
      meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'UNVERIFIED' }],
      meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
      examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
      ipaUs: '/roʊˈbʌst/', ipaStatus: 'VERIFIED',
      cambridgeUrl: 'https://dictionary.cambridge.org/dictionary/english/robust', cambridgeStatus: 'UNVERIFIED',
      verificationSummary: 'UNVERIFIED' }],
  };
}
function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ETag: '"synthetic"' } });
}
function failure(code: string, status = 503, operationId?: string) {
  return response({ error: { code, message: '<script>private provider body</script>', requestId: 'req_synthetic',
    ...(operationId ? { details: { kind: 'RETRY', operationId } } : {}) } }, status);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
let root: Root;
let container: HTMLDivElement;
let consent: View;
let requests: { url: string; init: RequestInit }[];
let lookup: (init: RequestInit) => Promise<Response>;
let operation: () => Promise<Response>;
async function mount(shell = false) {
  await act(async () => root.render(shell ? <AppShell currentPath="/lookup" /> :
    <AiConsentProvider><LookupPage /><AiConsentPanel /></AiConsentProvider>));
}
function input() { return container.querySelector<HTMLInputElement>('#lookup-term')!; }
function button(label: string) {
  const found = [...document.querySelectorAll('button')].find(item => item.textContent === label);
  if (!found) throw new Error(`Missing button ${label}`);
  return found;
}
async function click(label: string) { await act(async () => button(label).click()); }
async function edit(value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(), value);
    input().dispatchEvent(new Event('input', { bubbles: true }));
  });
}
const posts = () => requests.filter(item => item.url === '/api/v1/lookups' && item.init.method === 'POST');
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  consent = view(); requests = [];
  lookup = async () => response(preview());
  operation = async () => response({ operationId: 'op_synthetic', kind: 'LOOKUP', status: 'FAILED',
    createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    requests.push({ url, init });
    if (url === '/api/v1/ai-consent') {
      if (init.method === 'PUT' || init.method === 'DELETE') {
        consent = view(init.method === 'PUT' ? 'GRANTED' : 'REVOKED', consent.revision + 1);
        return response({ operationId: 'op_consent', appliedRevision: consent.revision });
      }
      return response(consent);
    }
    if (url === '/api/v1/lookups') return lookup(init);
    if (url.startsWith('/api/v1/operations/')) return operation();
    throw new Error('Unexpected request');
  }));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('T009 real client and consent boundary', () => {
  it('starts idle without lookup or persistence requests', async () => {
    await mount(); expect(input().value).toBe(''); expect(container.textContent).toContain('Nhập từ');
    expect(posts()).toHaveLength(0);
    expect(requests.every(item => item.url === '/api/v1/ai-consent')).toBe(true);
  });
  it.each(['', '   ', 'a'.repeat(81), 'bad\u0000term', 'bad\u0085term', '\ud800'])('rejects invalid term %j without POST', async term => {
    await mount(); await edit(term); await click('Tra cứu');
    expect(input().getAttribute('aria-invalid')).toBe('true'); expect(document.activeElement).toBe(input());
    expect(input().value).toBe(term); expect(posts()).toHaveLength(0);
  });
  it('preserves the term through decline and grant and only sends a new explicit action', async () => {
    consent = view('NOT_GRANTED', 0); await mount(); await edit('  robust  ');
    button('Tra cứu').focus(); await click('Tra cứu'); await click('Chưa đồng ý');
    expect(input().value).toBe('  robust  '); expect(posts()).toHaveLength(0);
    await click('Tra cứu'); await click('Đồng ý');
    expect(input().value).toBe('  robust  '); expect(posts()).toHaveLength(0);
    await click('Tra cứu'); expect(posts()).toHaveLength(1);
    expect(JSON.parse(String(posts()[0].init.body))).toEqual({ term: 'robust' });
    expect(posts()[0].init.credentials).toBe('same-origin');
    expect(new Headers(posts()[0].init.headers).get('X-Request-ID')).toBeTruthy();
  });
  it('shows the complete preview and never writes cards or sources', async () => {
    await mount(); await edit('robust'); await click('Tra cứu');
    for (const text of ['robust', 'ADJECTIVE', 'vững chắc', 'strong', 'A robust design.', 'Một thiết kế vững chắc.', '/roʊˈbʌst/', 'UNVERIFIED', 'lookup-v1', 'Chỉ xem trước']) {
      expect(container.textContent).toContain(text);
    }
    expect(document.activeElement?.id).toBe('lookup-status');
    expect(posts()).toHaveLength(1); expect(requests.every(item => ['/api/v1/lookups', '/api/v1/ai-consent'].includes(item.url))).toBe(true);
  });
  it('labels missing IPA and unverified links and renders hostile HTML only as text', async () => {
    const data = preview(); data.forms[0].ipaUs = null; data.forms[0].ipaStatus = 'MISSING';
    data.forms[0].meaningsVi[0].text = '<img src=x onerror=alert(1)>';
    data.forms[0].cambridgeUrl = 'javascript:alert(1)'; lookup = async () => response(data);
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain('MISSING'); expect(container.textContent).toContain('UNVERIFIED');
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(container.querySelector('img,script,a[href^="javascript:"]')).toBeNull();
  });
  it('blocks repeated clicks while loading and shows empty results truthfully', async () => {
    const held = deferred<Response>(); lookup = async () => held.promise;
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Tra cứu');
    expect(posts()).toHaveLength(1); expect(container.textContent).toContain('Đang tra cứu');
    const data = preview(); data.forms = [];
    await act(async () => held.resolve(response(data)));
    expect(container.textContent).toContain('Không có dạng từ'); expect(container.textContent).not.toContain('Đã có kết quả');
  });
  it('uses a fresh key only after confirmed terminal failure and explicit retry', async () => {
    lookup = async () => failure('BRIDGE_UNAVAILABLE', 503, 'op_synthetic');
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
    await click('Kiểm tra kết quả'); expect(container.textContent).toContain('Thao tác đã thất bại');
    lookup = async () => response(preview()); await click('Thử lại');
    expect(posts()).toHaveLength(2);
    expect(new Headers(posts()[0].init.headers).get('Idempotency-Key')).not.toBe(new Headers(posts()[1].init.headers).get('Idempotency-Key'));
  });
  it('reconciles lost responses using the original body and key without inventing success', async () => {
    lookup = async () => { throw new TypeError('Synthetic lost response'); };
    await mount(); await edit('robust'); await click('Tra cứu'); await edit('other');
    expect(container.textContent).toContain('Chưa xác định'); expect(button('Tra cứu').disabled).toBe(true);
    lookup = async () => response(preview()); await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(2); expect(posts()[0].init.body).toBe(posts()[1].init.body);
    expect(new Headers(posts()[0].init.headers).get('Idempotency-Key')).toBe(new Headers(posts()[1].init.headers).get('Idempotency-Key'));
    expect(input().value).toBe('other'); expect(container.textContent).not.toContain('vững chắc');
  });
  it('discards a stale success after edits and permits a fresh explicit action', async () => {
    const held = deferred<Response>(); lookup = async () => held.promise;
    await mount(); await edit('robust'); await click('Tra cứu'); await edit('other');
    await act(async () => held.resolve(response(preview())));
    expect(input().value).toBe('other'); expect(container.textContent).not.toContain('vững chắc'); expect(posts()).toHaveLength(1);
    lookup = async () => response({ ...preview(), term: 'other' }); await click('Tra cứu'); expect(posts()).toHaveLength(2);
  });
  it('does not dispatch a delayed authorization after the input changes', async () => {
    await mount(); await edit('robust'); const held = deferred<Response>();
    vi.mocked(fetch).mockImplementationOnce(async () => held.promise);
    await click('Tra cứu'); await edit('other');
    await act(async () => held.resolve(response(consent)));
    expect(posts()).toHaveLength(0); expect(input().value).toBe('other');
  });
  it.each(['BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE', 'CONFIGURATION_REQUIRED', 'SESSION_REQUIRED'])('maps %s safely without provider details', async code => {
    lookup = async () => failure(code, code === 'SESSION_REQUIRED' ? 401 : 503);
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain(code); expect(container.textContent).not.toContain('private provider body');
    expect(input().value).toBe('robust'); expect(posts()).toHaveLength(1);
  });
  it('treats malformed success as unknown and does not pass it to the renderer', async () => {
    lookup = async () => response({ ...preview(), forms: [{ lemma: 'bad' }] });
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).not.toContain('Đã có kết quả');
  });
  it('preserves a term and pending receipt across real shell navigation without restored dispatch', async () => {
    await mount(true); const held = deferred<Response>(); lookup = async () => held.promise;
    await edit('robust'); await click('Tra cứu');
    await act(async () => root.render(<AppShell currentPath="/status" />));
    await act(async () => held.resolve(response(preview())));
    await act(async () => root.render(<AppShell currentPath="/lookup" />));
    expect(input().value).toBe('robust'); expect(posts()).toHaveLength(1);
    expect(container.querySelector('main h1')?.textContent).toBe('Tra cứu từ vựng');
  });
  it('normalizes NFC and contract whitespace without rewriting the input', async () => {
    lookup = async () => response({ ...preview(), term: 'café robust' });
    await mount(); await edit('  cafe\u0301\u00a0  robust  '); await click('Tra cứu');
    expect(JSON.parse(String(posts()[0].init.body))).toEqual({ term: 'café robust' });
    expect(input().value).toBe('  cafe\u0301\u00a0  robust  ');
  });
  it('shows unavailable consent API and sends zero lookup POSTs', async () => {
    await mount(); await edit('robust');
    vi.mocked(fetch).mockImplementationOnce(async () => { throw new TypeError('Synthetic unavailable API'); });
    await click('Tra cứu'); expect(container.textContent).toContain('Không đọc được quyền AI');
    expect(posts()).toHaveLength(0); expect(input().value).toBe('robust');
  });
  it.each(['PENDING', 'UNKNOWN'] as const)('reconciles %s only by GET and cannot start a new operation', async status => {
    lookup = async () => failure('BRIDGE_UNAVAILABLE', 503, 'op_synthetic');
    operation = async () => response({ operationId: 'op_synthetic', kind: 'LOOKUP', status,
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Kiểm tra kết quả');
    expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
    expect(button('Tra cứu').disabled).toBe(true);
    expect(requests.filter(item => item.url === '/api/v1/operations/op_synthetic')).toHaveLength(1);
  });
  it('retrieves confirmed success with the original key even after revocation', async () => {
    lookup = async () => failure('BRIDGE_UNAVAILABLE', 503, 'op_synthetic');
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Rút lại quyền gửi dữ liệu AI');
    operation = async () => response({ operationId: 'op_synthetic', kind: 'LOOKUP', status: 'SUCCEEDED', resultRef: 'lookup_synthetic',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    lookup = async () => response(preview());
    const consentReads = requests.filter(item => item.url === '/api/v1/ai-consent').length;
    await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(2); expect(posts()[0].init.body).toBe(posts()[1].init.body);
    expect(new Headers(posts()[0].init.headers).get('Idempotency-Key')).toBe(new Headers(posts()[1].init.headers).get('Idempotency-Key'));
    expect(container.textContent).toContain('vững chắc');
    expect(requests.filter(item => item.url === '/api/v1/ai-consent')).toHaveLength(consentReads);
  });
  it('preserves an unknown intent on pre-ledger replay rejection', async () => {
    lookup = async () => { throw new TypeError('Synthetic response lost'); };
    await mount(); await edit('robust'); await click('Tra cứu');
    lookup = async () => failure('SESSION_REQUIRED', 401); await click('Kiểm tra kết quả');
    expect(container.textContent).toContain('Chưa xác định'); expect(button('Tra cứu').disabled).toBe(true);
    lookup = async () => response(preview()); await click('Kiểm tra kết quả');
    expect(posts()).toHaveLength(3);
    expect(new Set(posts().map(item => new Headers(item.init.headers).get('Idempotency-Key'))).size).toBe(1);
  });
  it.each(['BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE'])('settles lost terminal %s replay before an explicit fresh retry', async code => {
    lookup = async () => { throw new TypeError('Synthetic response lost'); };
    await mount(); await edit('robust'); await click('Tra cứu');
    lookup = async () => failure(code, 502); await click('Kiểm tra kết quả');
    expect(container.textContent).toContain('Thao tác đã thất bại');
    lookup = async () => response(preview()); await click('Thử lại');
    const keys = posts().map(item => new Headers(item.init.headers).get('Idempotency-Key'));
    expect(keys[0]).toBe(keys[1]); expect(keys[2]).not.toBe(keys[1]);
  });
  it.each([{ status: ['FAILED'] }, { status: { toString: 'FAILED' } }, { status: null }])('rejects a non-string status %j without false success', async ({ status }) => {
    lookup = async () => response({ ...preview(), status });
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).not.toContain('Đã có kết quả');
  });
  it.each(['javascript:alert(1)', 'data:text/html,hostile', 'https://dictionary.cambridge.org.evil.example/dictionary/english/robust',
    'https://user:pass@dictionary.cambridge.org/dictionary/english/robust', 'http://dictionary.cambridge.org/dictionary/english/robust',
    'https://dictionary.cambridge.org:8443/dictionary/english/robust'])('does not activate unsafe reference %s', async url => {
    const data = preview(); data.forms[0].cambridgeUrl = url; lookup = async () => response(data);
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.querySelector('a')).toBeNull(); expect(container.textContent).toContain('Liên kết không an toàn');
  });
  it('renders every form and every meaning without merging parts of speech', async () => {
    const data = preview(); data.forms[0].meaningsVi.push({ text: 'đáng tin cậy', language: 'vi', verificationStatus: 'UNVERIFIED' });
    data.forms.push({ ...data.forms[0], formId: 'draft_second', lemma: 'robustly', partOfSpeech: 'ADVERB' });
    lookup = async () => response(data); await mount(); await edit('robust'); await click('Tra cứu');
    expect([...container.querySelectorAll('h3')].map(item => item.textContent)).toEqual(['robust', 'robustly']);
    expect(container.textContent).toContain('ADJECTIVE'); expect(container.textContent).toContain('ADVERB'); expect(container.textContent).toContain('đáng tin cậy');
  });
  it('revokes during a pending lookup without retrying or replacing the draft', async () => {
    const held = deferred<Response>(); lookup = async () => held.promise;
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Rút lại quyền gửi dữ liệu AI');
    await act(async () => held.resolve(response(preview())));
    expect(consent.state).toBe('REVOKED'); expect(input().value).toBe('robust'); expect(posts()).toHaveLength(1);
    await click('Tra cứu'); expect(posts()).toHaveLength(1); expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  });
  it('stops waiting without discarding the operation key or claiming cancellation upstream', async () => {
    lookup = async init => new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Synthetic abort', 'AbortError')), { once: true });
    });
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Dừng chờ kết quả');
    expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
    lookup = async () => response(preview()); await click('Kiểm tra kết quả');
    expect(new Headers(posts()[0].init.headers).get('Idempotency-Key')).toBe(new Headers(posts()[1].init.headers).get('Idempotency-Key'));
  });
  it('navigation invalidates delayed consent authorization without dispatch on restoration', async () => {
    await mount(true); await edit('robust'); const held = deferred<Response>();
    vi.mocked(fetch).mockImplementationOnce(async () => held.promise); await click('Tra cứu');
    await act(async () => root.render(<AppShell currentPath="/review" />));
    await act(async () => held.resolve(response(consent)));
    await act(async () => root.render(<AppShell currentPath="/lookup" />));
    expect(input().value).toBe('robust'); expect(posts()).toHaveLength(0);
  });
  it('keeps the operation unknown at the 120 second client deadline with no background retry', async () => {
    vi.useFakeTimers();
    try {
      lookup = async init => new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new DOMException('Synthetic deadline', 'AbortError')), { once: true });
      });
      await mount(); await edit('robust'); await click('Tra cứu');
      await act(async () => vi.advanceTimersByTimeAsync(119_999));
      expect(container.textContent).toContain('Đang tra cứu'); expect(posts()).toHaveLength(1);
      await act(async () => vi.advanceTimersByTimeAsync(1));
      expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
      await act(async () => vi.advanceTimersByTimeAsync(120_000)); expect(posts()).toHaveLength(1);
    } finally { vi.useRealTimers(); }
  });
  it('rejects a mismatched or malformed operation receipt and retains the same intent', async () => {
    lookup = async () => failure('BRIDGE_UNAVAILABLE', 503, 'op_synthetic');
    operation = async () => response({ operationId: 'op_other', kind: 'LOOKUP', status: 'FAILED',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await mount(); await edit('robust'); await click('Tra cứu'); await click('Kiểm tra kết quả');
    expect(container.textContent).toContain('biên nhận thao tác không hợp lệ'); expect(posts()).toHaveLength(1);
    expect(button('Tra cứu').disabled).toBe(true);
  });
  it('settles FAILED preview without rendering success and requires explicit fresh retry', async () => {
    lookup = async () => response({ ...preview(), status: 'FAILED', forms: [] });
    await mount(); await edit('robust'); await click('Tra cứu');
    expect(container.textContent).toContain('Thao tác đã thất bại'); expect(container.querySelector('#lookup-preview-heading')).toBeNull();
    lookup = async () => response(preview()); await click('Thử lại');
    expect(posts()).toHaveLength(2);
    expect(new Headers(posts()[0].init.headers).get('Idempotency-Key')).not.toBe(new Headers(posts()[1].init.headers).get('Idempotency-Key'));
  });
  it('policy reconciliation alone makes zero lookup requests and preserves the term', async () => {
    await mount(); await edit('robust');
    consent = { ...consent, policy: { ...policy, digest: 'b'.repeat(64) } };
    await act(async () => window.dispatchEvent(new Event('focus')));
    expect(posts()).toHaveLength(0); expect(input().value).toBe('robust');
    await click('Tra cứu'); expect(posts()).toHaveLength(0);
    expect(document.body.textContent).toContain('Chưa hoàn tất chính sách AI');
  });
  it('disclosure dismissal keeps the term and never posts lookup', async () => {
    consent = view('NOT_GRANTED', 0); await mount(); await edit('robust');
    button('Tra cứu').focus(); await click('Tra cứu');
    await act(async () => document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
    await vi.waitFor(() => expect(document.activeElement).toBe(button('Tra cứu')));
    expect(posts()).toHaveLength(0); expect(input().value).toBe('robust');
  });
});
