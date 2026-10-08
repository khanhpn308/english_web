// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/shared/api/generated';
import { AiConsentGate, AiConsentProvider } from './AiConsentGate';
import { AiConsentPanel } from './AiConsentPanel';
import { AppShell } from '@/app/AppShell';

type View = components['schemas']['AiConsentView'];
const policy: NonNullable<View['policy']> = {
  version: 'synthetic-policy-v1', digest: 'a'.repeat(64), reviewStatus: 'READY',
  disclosureText: 'Synthetic disclosure <script>plain text</script>',
  dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'], recipients: ['Synthetic recipient'],
  retentionStatement: 'Synthetic retention limitation', regionStatement: 'Synthetic region limitation',
  costQuotaStatement: 'Synthetic quota and entitlement limitation', withdrawalStatement: 'Synthetic withdrawal limitation',
  scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [],
  dispatchRules: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'].map(scope => ({
    scope: scope as components['schemas']['AiDispatchRule']['scope'],
    providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high',
    route: 'primary', billingMode: 'configured-account',
  })),
};
function view(state: View['state'] = 'NOT_GRANTED', revision = 0): View {
  return { state, revision, policy, canRequestAi: state === 'GRANTED',
    acceptedPolicyVersion: state === 'GRANTED' ? policy.version : null,
    acceptedPolicyDigest: state === 'GRANTED' ? policy.digest : null,
    lastChoiceAt: revision ? '2026-10-08T00:00:00Z' : null };
}
function response(data: unknown, status = 200, etag = '"synthetic-etag"') {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ETag: etag } });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
let root: Root;
let container: HTMLDivElement;
let current: View;
let requests: { url: string; init: RequestInit }[];
let mutate: (init: RequestInit) => Promise<Response>;
const dispatched = vi.fn();
async function mount(shell = false) {
  await act(async () => root.render(shell ? <AppShell currentPath="/status" /> :
    <AiConsentProvider><AiConsentPanel /><AiConsentGate onAuthorized={dispatched}>Synthetic AI action</AiConsentGate></AiConsentProvider>));
}
function button(text: string) {
  const found = [...document.querySelectorAll('button')].find(item => item.textContent === text);
  if (!found) throw new Error(`Missing button ${text}`);
  return found;
}
async function click(text: string) { await act(async () => button(text).click()); }
async function focusWindow() { await act(async () => window.dispatchEvent(new Event('focus'))); }
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  current = view(); requests = []; dispatched.mockClear();
  mutate = async init => {
    current = view(init.method === 'DELETE' ? 'REVOKED' : 'GRANTED', current.revision + 1);
    return response({ appliedRevision: current.revision, operationId: 'op_synthetic' });
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    requests.push({ url, init });
    return init.method === 'PUT' || init.method === 'DELETE' ? mutate(init) : response(current);
  }));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('T018 consent behavior', () => {
  it.each(['NOT_GRANTED', 'GRANTED', 'REVOKED', 'STALE'] as const)('renders %s from authoritative GET', async state => {
    current = view(state, state === 'NOT_GRANTED' ? 0 : 1); await mount();
    expect(container.textContent).toContain(state);
    expect(requests.every(item => item.url === '/api/v1/ai-consent')).toBe(true);
  });
  it('renders every structured disclosure field as plain text in the real status route', async () => {
    await mount(true);
    for (const field of [policy.version, policy.digest, ...policy.recipients, policy.retentionStatement,
      policy.regionStatement, policy.costQuotaStatement, policy.withdrawalStatement, ...policy.scopes,
      ...policy.dataCategories, 'Antigravity/Google', 'gemini-3.8-flash-high', 'primary', 'configured-account']) {
      expect(container.textContent).toContain(field);
    }
    expect(container.querySelector('#ai-consent')).not.toBeNull();
    expect(container.querySelector('script')).toBeNull();
  });
  it('declines without writes and restores focus after Escape', async () => {
    await mount(); const trigger = button('Xem chính sách AI'); trigger.focus(); await click('Xem chính sách AI');
    expect(document.activeElement?.textContent).toBe('Quyền gửi dữ liệu AI');
    await act(async () => document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await vi.waitFor(() => expect(document.activeElement).toBe(trigger));
    expect(requests.every(item => !item.init.method)).toBe(true);
    expect(dispatched).not.toHaveBeenCalled();
  });
  it('grants with the shown ETag, then requires a fresh AI action', async () => {
    await mount(); await click('Synthetic AI action'); await click('Đồng ý');
    const put = requests.find(item => item.init.method === 'PUT');
    expect(new Headers(put?.init.headers).get('If-Match')).toBe('"synthetic-etag"');
    expect(JSON.parse(String(put?.init.body))).toEqual({ policyVersion: policy.version });
    expect(container.textContent).toContain('GRANTED'); expect(dispatched).not.toHaveBeenCalled();
    await click('Synthetic AI action'); expect(dispatched).toHaveBeenCalledOnce();
    expect(requests.every(item => item.url === '/api/v1/ai-consent')).toBe(true);
  });
  it('does not bypass the gate by submitting a parent form', async () => {
    const submitted = vi.fn();
    await act(async () => root.render(<AiConsentProvider><AiConsentPanel />
      <form onSubmit={event => { event.preventDefault(); submitted(); }}>
        <AiConsentGate onAuthorized={dispatched}>Synthetic AI action</AiConsentGate>
      </form>
    </AiConsentProvider>));
    await click('Synthetic AI action'); expect(submitted).not.toHaveBeenCalled();
    expect(button('Synthetic AI action').type).toBe('button'); expect(dispatched).not.toHaveBeenCalled();
  });
  it.each([null, { ...policy, reviewStatus: 'BLOCKED' as const }, { ...policy, retentionStatement: '' },
    { ...policy, dispatchRules: [] }, { ...policy, scopes: ['LOOKUP'] as typeof policy.scopes }])(
    'prevents grant for missing, blocked or incomplete policy', async invalid => {
      current = { ...view(), policy: invalid }; await mount(); await click('Xem chính sách AI');
      expect(document.body.textContent).toContain('Chưa hoàn tất chính sách AI');
      expect([...document.querySelectorAll('button')].some(item => item.textContent === 'Đồng ý')).toBe(false);
      await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
    });
  it('denies same-version digest changes even if an inconsistent backend reports GRANTED', async () => {
    current = view('GRANTED', 1); await mount();
    current = { ...current, policy: { ...policy, digest: 'b'.repeat(64) }, acceptedPolicyDigest: 'b'.repeat(64) };
    await focusWindow(); expect(container.textContent).toContain('STALE');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('Chưa hoàn tất chính sách AI');
  });
  it('rejects a same-version digest mismatch on first load, and permits disclosure of a new version', async () => {
    current = { ...view('GRANTED', 1), state: 'STALE', policy: { ...policy, digest: 'b'.repeat(64) }, canRequestAi: false };
    await mount(); await click('Xem chính sách AI');
    expect(document.body.textContent).toContain('Chưa hoàn tất chính sách AI');
    expect([...document.querySelectorAll('button')].some(item => item.textContent === 'Đồng ý')).toBe(false);
    current = { ...current, policy: { ...policy, version: 'synthetic-policy-v2', digest: 'c'.repeat(64) } };
    await click('Đọc lại chính sách'); expect(button('Đồng ý').disabled).toBe(false);
    expect(document.body.textContent).toContain('synthetic-policy-v2'); expect(dispatched).not.toHaveBeenCalled();
  });
  it('keeps the original trigger for focus restoration after rereading disclosure', async () => {
    await mount(); const trigger = button('Xem chính sách AI'); trigger.focus();
    await click('Xem chính sách AI'); await click('Đọc lại chính sách'); await click('Chưa đồng ý');
    await vi.waitFor(() => expect(document.activeElement).toBe(trigger));
  });
  it('rejects stale-tab grant with typed conflict and requires another explicit disclosure', async () => {
    await mount(); await click('Xem chính sách AI');
    mutate = async () => { current = view('REVOKED', 2); return response({ error: {
      code: 'REVISION_CONFLICT', message: 'Synthetic conflict', requestId: 'req_synthetic',
    } }, 409); };
    await click('Đồng ý');
    expect(document.body.textContent).toContain('REVISION_CONFLICT');
    expect(container.textContent).toContain('REVOKED'); expect(dispatched).not.toHaveBeenCalled();
    expect([...document.querySelectorAll('button')].some(item => item.textContent === 'Đồng ý')).toBe(false);
    await click('Đọc lại chính sách'); expect(button('Đồng ý').disabled).toBe(false);
    expect(requests.filter(item => item.init.method === 'PUT')).toHaveLength(1);
  });
  it('reconciles lost grant from GET without sending learning content or requiring another mutation', async () => {
    await mount(); await click('Xem chính sách AI');
    mutate = async () => { current = view('GRANTED', 1); throw new TypeError('Synthetic response lost'); };
    await click('Đồng ý');
    expect(container.textContent).toContain('Đã lưu quyền gửi dữ liệu AI');
    expect(container.querySelector('[role="alert"]')).toBeNull(); expect(dispatched).not.toHaveBeenCalled();
    await click('Synthetic AI action'); expect(dispatched).toHaveBeenCalledOnce();
    expect(requests.filter(item => item.init.method === 'PUT')).toHaveLength(1);
  });
  it('retains the same unknown grant fingerprint on explicit replay and prevents duplicate pending grant', async () => {
    await mount(); await click('Xem chính sách AI');
    const held = deferred<Response>(); mutate = async () => held.promise;
    await click('Đồng ý'); expect(button('Chưa đồng ý').disabled).toBe(false);
    expect(requests.filter(item => item.init.method === 'PUT')).toHaveLength(1);
    await act(async () => held.resolve(response(null)));
    expect(document.body.textContent).toContain('Chưa xác nhận đồng ý');
    await click('Chưa đồng ý');
    mutate = async () => { current = view('GRANTED', 1); return response({ appliedRevision: 1, operationId: 'op_replay' }); };
    await click('Thử lại cùng thao tác');
    const puts = requests.filter(item => item.init.method === 'PUT');
    expect(puts).toHaveLength(2); expect(puts[0].init.body).toBe(puts[1].init.body);
    expect(new Headers(puts[0].init.headers).get('Idempotency-Key')).toBe(new Headers(puts[1].init.headers).get('Idempotency-Key'));
    expect(new Headers(puts[0].init.headers).get('If-Match')).toBe(new Headers(puts[1].init.headers).get('If-Match'));
    expect(dispatched).not.toHaveBeenCalled();
  });
  it('ignores historical grant receipts after withdrawal', async () => {
    await mount(); mutate = async () => { current = view('REVOKED', 2); return response({ appliedRevision: 1, operationId: 'op_old' }); };
    await click('Xem chính sách AI'); await click('Đồng ý');
    expect(container.textContent).toContain('REVOKED'); expect(dispatched).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain('Đã lưu quyền gửi dữ liệu AI');
  });
  it('blocks AI immediately during revoke and rejects an older in-flight authorization read', async () => {
    current = view('GRANTED', 1); await mount();
    const heldRead = deferred<Response>(); const heldWrite = deferred<Response>();
    vi.mocked(fetch).mockImplementationOnce(async () => heldRead.promise);
    await click('Synthetic AI action'); mutate = async () => heldWrite.promise;
    await click('Rút lại quyền gửi dữ liệu AI');
    await act(async () => heldRead.resolve(response(view('GRANTED', 1))));
    expect(dispatched).not.toHaveBeenCalled();
    expect(container.textContent).toContain('Đang rút quyền');
    current = view('REVOKED', 2);
    await act(async () => heldWrite.resolve(response({ appliedRevision: 2, operationId: 'op_revoke' })));
    expect(container.textContent).toContain('Đã chặn các yêu cầu AI mới');
  });
  it('reconciles a lost revoke response from durable GET without false success', async () => {
    current = view('GRANTED', 1); await mount(); mutate = async () => { current = view('REVOKED', 2); throw new TypeError('Synthetic lost response'); };
    await click('Rút lại quyền gửi dữ liệu AI');
    expect(container.textContent).toContain('Đã chặn các yêu cầu AI mới');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
  });
  it('keeps failed revoke unresolved through focus and replays exactly the same intent', async () => {
    current = view('GRANTED', 1); await mount(); mutate = async () => { throw new TypeError('Synthetic connection loss'); };
    await click('Rút lại quyền gửi dữ liệu AI'); await focusWindow();
    expect(container.textContent).toContain('Chưa xác nhận rút quyền');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
    await click('Thử lại cùng thao tác');
    const deletes = requests.filter(item => item.init.method === 'DELETE');
    expect(deletes).toHaveLength(2);
    expect(new Headers(deletes[0].init.headers).get('Idempotency-Key')).toBe(new Headers(deletes[1].init.headers).get('Idempotency-Key'));
    expect(new Headers(deletes[0].init.headers).has('If-Match')).toBe(false);
    expect(deletes[0].init.body).toBeUndefined();
  });
  it('allows offline revoke with null policy and surfaces typed storage failure', async () => {
    current = { ...view('STALE', 1), policy: null }; await mount();
    mutate = async () => response({ error: { code: 'STORAGE_BUSY', message: 'Synthetic failure', requestId: 'req_synthetic' } }, 503);
    await click('Rút lại quyền gửi dữ liệu AI');
    expect(container.textContent).toContain('Chưa xác nhận rút quyền');
    expect(container.textContent).toContain('STORAGE_BUSY');
    expect(requests.filter(item => item.init.method === 'DELETE')).toHaveLength(1);
  });
  it('does not claim success when revoke receipt is followed by a failed GET', async () => {
    current = view('GRANTED', 1); await mount();
    mutate = async () => {
      vi.mocked(fetch).mockImplementationOnce(async () => { throw new TypeError('Synthetic API stopped'); });
      return response({ appliedRevision: 2, operationId: 'op_synthetic' });
    };
    await click('Rút lại quyền gửi dữ liệu AI');
    expect(container.textContent).toContain('Chưa xác nhận rút quyền');
    expect(container.textContent).not.toContain('Đã chặn các yêu cầu AI mới');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
    current = view('REVOKED', 2); await click('Đọc lại trạng thái');
    expect(container.textContent).toContain('Đã chặn các yêu cầu AI mới');
  });
  it('does not infer a failed revoke succeeded from a historical revoked row when the prior read failed', async () => {
    vi.mocked(fetch).mockImplementationOnce(async () => { throw new TypeError('Synthetic initial read failure'); });
    await mount(); current = view('REVOKED', 2);
    mutate = async () => { throw new TypeError('Synthetic response loss'); };
    await click('Rút lại quyền gửi dữ liệu AI');
    expect(container.textContent).toContain('REVOKED');
    expect(container.textContent).toContain('Chưa xác nhận rút quyền');
    expect(container.textContent).not.toContain('Đã chặn các yêu cầu AI mới');
  });
  it('ignores stale focus responses and checks permission again before an explicit action', async () => {
    current = view('GRANTED', 1); await mount();
    const oldRead = deferred<Response>(); vi.mocked(fetch).mockImplementationOnce(async () => oldRead.promise);
    await focusWindow(); current = view('REVOKED', 2); await focusWindow();
    await act(async () => oldRead.resolve(response(view('GRANTED', 1))));
    expect(container.textContent).toContain('REVOKED');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
  });
  it('blocks grant after a failed policy refresh and recovers with a deliberate reread', async () => {
    await mount(); await click('Xem chính sách AI');
    vi.mocked(fetch).mockImplementationOnce(async () => { throw new TypeError('Synthetic lost GET'); });
    await focusWindow(); expect(document.body.textContent).toContain('Không đọc được quyền AI');
    expect([...document.querySelectorAll('button')].some(item => item.textContent === 'Đồng ý')).toBe(false);
    await click('Đọc lại chính sách'); expect(button('Đồng ý').disabled).toBe(false);
    expect(requests.filter(item => item.init.method === 'PUT')).toHaveLength(0);
  });
  it('requires the authoritative GET precondition instead of constructing a missing ETag', async () => {
    vi.mocked(fetch).mockImplementation(async () => new Response(JSON.stringify(view('GRANTED', 1)), {
      headers: { 'Content-Type': 'application/json' },
    }));
    await mount(); expect(container.textContent).toContain('Không đọc được quyền AI');
    await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
  });
  it.each([null, {}, { ...view('GRANTED', 1), revision: -1 }, { ...view('GRANTED', 1), lastChoiceAt: 'invalid' }])(
    'treats malformed GET as an error, never permission', async malformed => {
      vi.mocked(fetch).mockImplementation(async () => response(malformed)); await mount();
      expect(container.textContent).toContain('Không đọc được quyền AI');
      await click('Synthetic AI action'); expect(dispatched).not.toHaveBeenCalled();
    });
  it('shows loading and recoverable read errors, never reading browser storage as permission', async () => {
    const held = deferred<Response>(); vi.mocked(fetch).mockImplementationOnce(async () => held.promise);
    const storageRead = vi.spyOn(Storage.prototype, 'getItem'); await mount();
    expect(container.textContent).toContain('Đang đọc quyền AI');
    await act(async () => held.resolve(response({ error: { code: 'SESSION_EXPIRED', message: 'Synthetic error', requestId: 'req_synthetic' } }, 401)));
    expect(container.textContent).toContain('SESSION_EXPIRED');
    await click('Đọc lại trạng thái'); expect(container.textContent).toContain('NOT_GRANTED');
    expect(storageRead).not.toHaveBeenCalled(); storageRead.mockRestore();
  });
});
