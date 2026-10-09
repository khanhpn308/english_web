// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AudioButton } from './AudioButton';
import { SavePreview } from './SavePreview';
import type { components } from '@/shared/api/generated';

const voice = (lang = 'en-US', localService = true): SpeechSynthesisVoice => ({
  lang, localService, name: 'Synthetic voice', voiceURI: `synthetic-${lang}`, default: true,
});
class SyntheticUtterance {
  text: string;
  lang = '';
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) { this.text = text; }
}
let root: Root;
let container: HTMLDivElement;
let voices: SpeechSynthesisVoice[];
let events: EventTarget;
let spoken: SyntheticUtterance[];
let cancel: ReturnType<typeof vi.fn>;
let fetchSpy: ReturnType<typeof vi.fn>;
const button = () => container.querySelector('button')!;
async function mount(active = true, text = 'robust') {
  await act(async () => root.render(<AudioButton text={text} active={active} />));
}
async function click() { await act(async () => button().click()); }
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers();
  sessionStorage.clear();
  container = document.createElement('div'); document.body.append(container);
  root = createRoot(container); voices = [voice()]; events = new EventTarget(); spoken = [];
  cancel = vi.fn(); fetchSpy = vi.fn(); vi.stubGlobal('fetch', fetchSpy);
  vi.stubGlobal('SpeechSynthesisUtterance', SyntheticUtterance);
  vi.stubGlobal('speechSynthesis', {
    getVoices: () => voices, cancel,
    speak: vi.fn((utterance: SyntheticUtterance) => spoken.push(utterance)),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  });
});

type Preview = components['schemas']['LookupResult'];
type Receipt = components['schemas']['SaveResult'];
type Source = components['schemas']['SourceFileView'];
const savePreview: Preview = {
  lookupId: 'lookup_fixture', operationId: 'op_lookup_fixture', term: 'robust', status: 'PREVIEW',
  provider: 'Synthetic provider', model: 'synthetic-model', promptVersion: 'fixture-v1',
  createdAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED',
  forms: [{ formId: 'draft_fixture', lemma: 'robust', partOfSpeech: 'ADJECTIVE',
    meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'UNVERIFIED' }],
    meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
    examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
    ipaUs: null, ipaStatus: 'MISSING', cambridgeUrl: null, cambridgeStatus: 'MISSING', verificationSummary: 'UNVERIFIED' }],
};
const sourceFixture: Source = { id: 'src_fixture', noteDate: '2026-10-09', revision: 7,
  etag: '"opaque-fixture-r7"', status: 'VALID', relativePath: '09-10-2026.md' };
function saveReceipt(reused = false): Receipt {
  const form = savePreview.forms[0];
  return { operationId: 'op_save_fixture', sourceId: 'src_fixture', sourceRevision: 8,
    sourceEtag: '"opaque-fixture-r8"', noteDate: '2026-10-09', markdownSync: 'COMPLETED',
    savedForms: [{ id: 'wf_fixture', revision: 1 }],
    canonicalForms: [{ id: 'wf_fixture', familyId: 'family_fixture', revision: 1,
      lemma: form.lemma, partOfSpeech: form.partOfSpeech, meaningsEn: form.meaningsEn,
      meaningsVi: form.meaningsVi, examples: form.examples, ipaUs: null, cambridgeUrl: null,
      verificationSummary: 'UNVERIFIED', updatedAt: '2026-10-09T00:00:00Z',
      sourceRefs: [{ sourceId: 'src_fixture', noteDate: '2026-10-09', status: 'VALID' }],
      card: { id: 'card_fixture', state: reused ? 'LEARNED' : 'NEW', dueAt: reused ? '2026-10-10T00:00:00Z' : null } }],
    createdCardIds: reused ? [] : ['card_fixture'], reusedCardIds: reused ? ['card_fixture'] : [] };
}
function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}
function saveError(code: string, status: number, details?: components['schemas']['ErrorDetails']) {
  return json({ error: { code, message: 'Synthetic redacted error', requestId: 'req_fixture', details } }, status);
}
function pending<T>() {
  let resolve!: (value: T) => void;
  return { promise: new Promise<T>(done => { resolve = done; }), resolve: (value: T) => resolve(value) };
}

describe('T025 Save receipts and recovery', () => {
  let sources: Source[];
  let save: (init: RequestInit) => Promise<Response>;
  let operation: () => Promise<Response>;
  let sourceRead: (url: string) => Promise<Response>;
  let requests: { url: string; init: RequestInit }[];
  const posts = () => requests.filter(entry => entry.url === '/api/v1/word-forms');
  const control = (label: string) => {
    const found = [...container.querySelectorAll('button')].find(entry => entry.textContent === label);
    if (!found) throw new Error(`Missing control: ${label}`);
    return found;
  };
  const press = async (label: string) => { await act(async () => control(label).click()); };
  const renderSave = async (preview: Preview | null = savePreview, active = true) => {
    await act(async () => root.render(<SavePreview preview={preview ?? undefined} active={active} />));
  };
  const changeDate = async (value: string) => {
    await act(async () => {
      const input = container.querySelector<HTMLInputElement>('input[type="date"]')!;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  };
  const chooseDate = async (value: string) => { await changeDate(value); await press('Đọc nguồn'); };
  beforeEach(() => {
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-09T00:00:00Z'));
    sources = [sourceFixture]; requests = [];
    sourceRead = async url => json({ data: sources.filter(source => source.noteDate === new URL(url, 'http://localhost').searchParams.get('noteDate')),
      pagination: { hasMore: false, nextCursor: null, pageSize: 100 }, sort: { by: 'noteDate', direction: 'ASC' } });
    save = async () => json(saveReceipt(), 201);
    operation = async () => json({ operationId: 'op_save_fixture', kind: 'SAVE', status: 'SUCCEEDED',
      resultRef: 'op_save_fixture', createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      requests.push({ url, init });
      if (url.startsWith('/api/v1/sources?')) return sourceRead(url);
      if (url === '/api/v1/word-forms') return save(init);
      if (url === '/api/v1/operations/op_save_fixture') return operation();
      throw new Error(`Unexpected endpoint: ${url}`);
    }));
  });
  it('uses the exact existing source version and waits for a durable receipt, bounding rapid clicks', async () => {
    const delayed = pending<Response>(); save = () => delayed.promise;
    await renderSave(); await chooseDate('2026-10-09');
    expect(container.textContent).toContain('robust'); expect(container.textContent).toContain('UNVERIFIED');
    await act(async () => { control('Lưu để ôn').click(); control('Lưu để ôn').click(); });
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(String(posts()[0].init.body))).toEqual({ lookupId: 'lookup_fixture', noteDate: '2026-10-09', sourceId: 'src_fixture', sourceRevision: 7 });
    const headers = new Headers(posts()[0].init.headers);
    expect(headers.get('If-Match')).toBe(sourceFixture.etag); expect(headers.has('If-None-Match')).toBe(false);
    expect(control('Đang lưu…').disabled).toBe(true);
    expect(container.textContent).not.toContain('Đã lưu để ôn');
    await act(async () => delayed.resolve(json(saveReceipt(), 201)));
    expect(container.textContent).toContain('Đã lưu để ôn');
    expect(container.textContent).toContain('op_save_fixture'); expect(container.textContent).toContain('Thẻ mới: 1');
    expect(container.textContent).toContain('vững chắc'); expect(container.textContent).toContain('A robust design.');
    expect(control('Đã lưu ngày này').disabled).toBe(true);
    await press('Kiểm tra biên nhận');
    expect(posts()).toHaveLength(2);
    expect(posts()[1].init.body).toBe(posts()[0].init.body);
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key')).toBe(headers.get('Idempotency-Key'));
  });
  it('sends conditional absence without source identity and reports card reuse truthfully', async () => {
    sources = []; save = async () => json({ ...saveReceipt(true), sourceRevision: 1 }, 201);
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(JSON.parse(String(posts()[0].init.body))).toEqual({ lookupId: 'lookup_fixture', noteDate: '2026-10-09' });
    const headers = new Headers(posts()[0].init.headers);
    expect(headers.get('If-None-Match')).toBe('*'); expect(headers.has('If-Match')).toBe(false);
    expect(container.textContent).toContain('Thẻ mới: 0'); expect(container.textContent).toContain('Thẻ dùng lại: 1');
    expect(container.textContent).toContain('LEARNED');
  });
  it('retains the preview on conflict and requires a fresh read and explicit Save for changed preconditions', async () => {
    save = async () => saveError('REVISION_CONFLICT', 409, { kind: 'CONFLICT', resourceType: 'SOURCE', resourceId: 'src_fixture', expectedRevision: 7, currentRevision: 8 });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('7'); expect(container.textContent).toContain('8');
    expect(container.textContent).toContain('robust'); expect(container.textContent).not.toContain('Đã lưu để ôn');
    expect(control('Lưu để ôn').disabled).toBe(true);
    const key = new Headers(posts()[0].init.headers).get('Idempotency-Key');
    sources = [{ ...sourceFixture, revision: 8, etag: '"opaque-fixture-r8"' }];
    save = async () => json({ ...saveReceipt(), sourceRevision: 9, sourceEtag: '"opaque-fixture-r9"' }, 201);
    await press('Đọc lại nguồn'); expect(posts()).toHaveLength(1);
    await press('Lưu để ôn');
    expect(JSON.parse(String(posts()[1].init.body)).sourceRevision).toBe(8);
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key')).not.toBe(key);
  });
  it('restores a lost-response intent after reload and explicitly replays identical intent without a new key', async () => {
    save = async () => { throw new TypeError('Synthetic disconnect'); };
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).not.toContain('Đã lưu để ôn');
    const first = posts()[0];
    await act(async () => root.render(null)); await renderSave(null);
    expect(posts()).toHaveLength(1);
    save = async () => json(saveReceipt(), 201);
    await press('Kiểm tra kết quả lưu');
    expect(posts()[1].init.body).toBe(first.init.body);
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key')).toBe(new Headers(first.init.headers).get('Idempotency-Key'));
    expect(container.textContent).toContain('Đã lưu để ôn');
  });
  it.each(['PENDING', 'UNKNOWN'] as const)('keeps %s operation unresolved and does not replay a mutation', async status => {
    save = async () => saveError('IDEMPOTENCY_IN_FLIGHT', 409, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    operation = async () => json({ operationId: 'op_save_fixture', kind: 'SAVE', status,
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn'); await press('Kiểm tra kết quả lưu');
    expect(posts()).toHaveLength(1); expect(container.textContent).not.toContain('Đã lưu để ôn');
    expect(container.querySelector<HTMLInputElement>('input')!.disabled).toBe(true);
  });
  it('fetches operation success then retrieves its original Save receipt', async () => {
    save = async () => saveError('STORAGE_BUSY', 503, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    save = async () => json(saveReceipt(), 201); await press('Kiểm tra kết quả lưu');
    expect(requests.some(entry => entry.url === '/api/v1/operations/op_save_fixture')).toBe(true);
    expect(container.textContent).toContain('Đã lưu để ôn');
  });
  it.each(['VALIDATION_ERROR', 'AI_CONSENT_REQUIRED', 'CONFIGURATION_REQUIRED'])('preserves content for %s and does not dispatch AI', async code => {
    save = async () => saveError(code, code === 'VALIDATION_ERROR' ? 422 : 403);
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain(code); expect(container.textContent).toContain('robust');
    expect(container.textContent).not.toContain('Đã lưu để ôn');
    expect(requests.some(entry => entry.url.includes('ai-consent') || entry.url.includes('lookups'))).toBe(false);
  });
  it.each(['INVALID', 'MISSING'] as const)('blocks writes to %s sources', async status => {
    sources = [{ ...sourceFixture, status, revision: status === 'MISSING' ? 0 : sourceFixture.revision }]; await renderSave(); await chooseDate('2026-10-09');
    expect(control('Lưu để ôn').disabled).toBe(true); expect(posts()).toEqual([]);
  });
  it('does not infer success from malformed or mismatched receipts, including a completed operation alone', async () => {
    save = async () => json({ ...saveReceipt(), markdownSync: 'PENDING' }, 201);
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).not.toContain('Đã lưu để ôn');
    save = async () => json({ ...saveReceipt(), noteDate: '2026-10-10' }, 201);
    await press('Kiểm tra kết quả lưu'); expect(container.textContent).not.toContain('Đã lưu để ôn');
  });
  it('retains uncertainty when reconciliation is rejected before receipt retrieval', async () => {
    save = async () => { throw new TypeError('Synthetic disconnect'); };
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    save = async () => saveError('SESSION_INVALID', 401); await press('Kiểm tra kết quả lưu');
    expect(container.textContent).toContain('Chưa xác định');
    expect(container.querySelector<HTMLInputElement>('input')!.disabled).toBe(true);
    expect(container.textContent).not.toContain('Đã lưu để ôn');
  });
  it('starts with an explicit source read and announces confirmation accessibly', async () => {
    await renderSave();
    expect(requests).toEqual([]); expect(control('Lưu để ôn').disabled).toBe(true);
    expect(container.querySelector('label')?.htmlFor).toBe(container.querySelector('input')?.id);
    await press('Đọc nguồn'); await press('Lưu để ôn');
    const announcement = container.querySelector('[aria-atomic="true"]');
    expect(announcement?.getAttribute('aria-live')).toBe('polite');
    expect(document.activeElement).toBe(announcement);
    expect(announcement?.textContent).toContain('Đã lưu để ôn');
  });
  it('permits another day after confirmation and preserves the original key on return', async () => {
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    const first = posts()[0];
    save = async () => {
      const receipt = saveReceipt(true);
      return json({ ...receipt, operationId: 'op_second_day', noteDate: '2026-10-10', sourceId: 'src_second_day', sourceRevision: 1,
        canonicalForms: receipt.canonicalForms.map(form => ({ ...form, sourceRefs: [{ sourceId: 'src_second_day', noteDate: '2026-10-10', status: 'VALID' }] })) }, 201);
    };
    await chooseDate('2026-10-10'); await press('Lưu để ôn');
    expect(container.textContent).toContain('op_second_day'); expect(container.textContent).toContain('Thẻ dùng lại: 1');
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key')).not.toBe(new Headers(first.init.headers).get('Idempotency-Key'));
    await changeDate('2026-10-09');
    expect(control('Đã lưu ngày này').disabled).toBe(true);
    const replay = pending<Response>(); save = () => replay.promise; await press('Kiểm tra biên nhận');
    expect(posts()[2].init.body).toBe(first.init.body);
    expect(new Headers(posts()[2].init.headers).get('Idempotency-Key')).toBe(new Headers(first.init.headers).get('Idempotency-Key'));
    expect(JSON.parse(sessionStorage.getItem('vocabulary.save-intent.v1')!).request.noteDate).toBe('2026-10-09');
    await act(async () => replay.resolve(json(saveReceipt())));
  });
  it('accepts the backend canonical display lemma for an existing form', async () => {
    const receipt = saveReceipt(true); receipt.canonicalForms[0].lemma = 'Robust';
    save = async () => json(receipt, 201);
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('Đã lưu để ôn'); expect(container.textContent).toContain('Robust');
    expect(container.textContent).toContain('Thẻ mới: 0');
  });
  it.each([
    ['missing meaning list', { canonicalForms: [{ ...saveReceipt().canonicalForms[0], meaningsEn: undefined }] }],
    ['missing a saved form', { savedForms: [] }],
    ['missing a canonical form', { canonicalForms: [] }],
    ['unmatched revisions', { savedForms: [{ id: 'wf_fixture', revision: 2 }] }],
    ['overlapping card classifications', { reusedCardIds: ['card_fixture'] }],
    ['unconfirmed card', { canonicalForms: [{ ...saveReceipt().canonicalForms[0], card: null }] }],
    ['wrong source', { sourceId: 'src_other' }],
    ['wrong source revision', { sourceRevision: 7 }],
  ] as const)('rejects an incomplete receipt: %s', async (_label, mutation) => {
    save = async () => json({ ...saveReceipt(), ...mutation }, 201);
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).not.toContain('Đã lưu để ôn');
    expect(control('Lưu để ôn').disabled).toBe(true);
    expect(control('Kiểm tra kết quả lưu').disabled).toBe(false);
  });
  it('does not accept a response ETag different from the receipt source ETag', async () => {
    save = async () => new Response(JSON.stringify(saveReceipt()), { status: 201,
      headers: { 'Content-Type': 'application/json', ETag: '"wrong-source-etag"' } });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('Chưa xác định'); expect(container.textContent).not.toContain('Đã lưu để ôn');
  });
  it.each([
    { kind: 'LOOKUP' }, { status: 'BROKEN' }, { operationId: 'op_other' }, { resultRef: 'op_other' },
  ])('keeps a malformed operation recoverable without replay: %j', async mutation => {
    save = async () => saveError('STORAGE_BUSY', 503, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    operation = async () => json({ operationId: 'op_save_fixture', kind: 'SAVE', status: 'SUCCEEDED', resultRef: 'op_save_fixture',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z', ...mutation });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn'); await press('Kiểm tra kết quả lưu');
    expect(posts()).toHaveLength(1); expect(container.textContent).toContain('Chưa xác định');
    expect(control('Kiểm tra kết quả lưu').disabled).toBe(false);
  });
  it('requires a reread and a new explicit intent only after a confirmed FAILED operation', async () => {
    save = async () => saveError('VALIDATION_ERROR', 422, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    operation = async () => json({ operationId: 'op_save_fixture', kind: 'SAVE', status: 'FAILED',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z' });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    const key = new Headers(posts()[0].init.headers).get('Idempotency-Key');
    await press('Kiểm tra kết quả lưu');
    expect(posts()).toHaveLength(1); expect(control('Lưu để ôn').disabled).toBe(true);
    expect(sessionStorage.getItem('vocabulary.save-intent.v1')).toBeNull();
    await press('Đọc lại nguồn'); save = async () => json(saveReceipt(), 201); await press('Lưu để ôn');
    expect(new Headers(posts()[1].init.headers).get('Idempotency-Key')).not.toBe(key);
  });
  it('retains the known Save operation when replay error metadata names another operation', async () => {
    save = async () => saveError('STORAGE_BUSY', 503, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    save = async () => saveError('STORAGE_BUSY', 503, { kind: 'RETRY', operationKind: 'LOOKUP', operationId: 'op_other' });
    await press('Kiểm tra kết quả lưu');
    expect(container.textContent).toContain('Chưa xác định');
    expect(JSON.parse(sessionStorage.getItem('vocabulary.save-intent.v1')!).operationId).toBe('op_save_fixture');
    expect(container.textContent).not.toContain('op_other');
  });
  it('bounds POST and operation read waits without a new mutation after timeout', async () => {
    save = init => new Promise((_resolve, reject) => init.signal!.addEventListener('abort', () => reject(new DOMException('Timed out', 'AbortError'))));
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(container.textContent).toContain('Chưa xác định'); expect(posts()).toHaveLength(1);
    save = async () => saveError('IDEMPOTENCY_IN_FLIGHT', 409, { kind: 'RETRY', operationKind: 'SAVE', operationId: 'op_save_fixture' });
    await press('Kiểm tra kết quả lưu');
    operation = () => new Promise((_resolve, reject) => {
      const signal = requests[requests.length - 1].init.signal!;
      signal.addEventListener('abort', () => reject(new DOMException('Timed out', 'AbortError')));
    });
    await press('Kiểm tra kết quả lưu'); await act(async () => vi.advanceTimersByTime(15_000));
    expect(posts()).toHaveLength(2); expect(control('Kiểm tra kết quả lưu').disabled).toBe(false);
    expect(container.textContent).not.toContain('Đã lưu để ôn');
  });
  it.each([
    { data: [sourceFixture, { ...sourceFixture, id: 'src_duplicate' }], pagination: { hasMore: false, nextCursor: null, pageSize: 100 } },
    { data: [], pagination: { hasMore: true, nextCursor: 'cursor_fixture', pageSize: 100 } },
    { data: [{ ...sourceFixture, noteDate: '2026-10-10' }], pagination: { hasMore: false, nextCursor: null, pageSize: 100 } },
  ])('blocks an ambiguous or incomplete source read: %j', async page => {
    sourceRead = async () => json(page);
    await renderSave(); await chooseDate('2026-10-09');
    expect(control('Lưu để ôn').disabled).toBe(true); expect(posts()).toEqual([]);
  });
  it('keeps a transient source read retry separate from mutation dispatch', async () => {
    sourceRead = async () => { throw new TypeError('Synthetic read failure'); };
    await renderSave(); await chooseDate('2026-10-09');
    expect(control('Lưu để ôn').disabled).toBe(true); expect(posts()).toEqual([]);
    sourceRead = async () => json({ data: [sourceFixture], pagination: { hasMore: false, nextCursor: null, pageSize: 100 } });
    await press('Đọc nguồn'); expect(control('Lưu để ôn').disabled).toBe(false); expect(posts()).toEqual([]);
  });
  it('blocks writes when an intent cannot be persisted before dispatch', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Storage disabled', 'SecurityError'); });
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(posts()).toEqual([]); expect(container.textContent).toContain('Chưa gửi yêu cầu');
  });
  it('does not replay extra untrusted stored headers or invent a replacement identity', async () => {
    sessionStorage.setItem('vocabulary.save-intent.v1', JSON.stringify({ request: { lookupId: 'lookup_fixture', noteDate: '2026-10-09' },
      headers: { 'Idempotency-Key': 'fixture-key', 'If-None-Match': '*', Authorization: 'untrusted' }, formCount: 1 }));
    await renderSave();
    expect(requests).toEqual([]); expect(control('Lưu để ôn').disabled).toBe(true);
    expect(container.textContent).toContain('Chưa xác định');
  });
  it('rejects an empty date locally and never fabricates source preconditions', async () => {
    await renderSave(); await changeDate('');
    expect(container.querySelector('input')?.getAttribute('aria-invalid')).toBe('true');
    expect(control('Đọc nguồn').disabled).toBe(true); expect(control('Lưu để ôn').disabled).toBe(true);
    expect(requests).toEqual([]);
  });
  it('allows the same source read again after leaving the page during a read', async () => {
    const delayed = pending<Response>(); sourceRead = () => delayed.promise;
    await renderSave(); await press('Đọc nguồn');
    expect(control('Đọc nguồn').disabled).toBe(true);
    await renderSave(savePreview, false);
    await act(async () => delayed.resolve(json({ data: [sourceFixture], pagination: { hasMore: false, nextCursor: null, pageSize: 100 } })));
    await renderSave();
    expect(control('Đọc nguồn').disabled).toBe(false); expect(control('Lưu để ôn').disabled).toBe(true);
    sourceRead = async () => json({ data: [sourceFixture], pagination: { hasMore: false, nextCursor: null, pageSize: 100 } });
    await press('Đọc nguồn'); expect(control('Lưu để ôn').disabled).toBe(false);
  });
  it('does not present a previous lookup receipt as success for a new preview', async () => {
    await renderSave(); await chooseDate('2026-10-09'); await press('Lưu để ôn');
    expect(container.textContent).toContain('Đã lưu để ôn');
    await renderSave({ ...savePreview, lookupId: 'lookup_other', term: 'different term' });
    expect(container.textContent).not.toContain('Đã lưu để ôn');
    expect(container.textContent).not.toContain('op_save_fixture');
    expect(control('Lưu để ôn').disabled).toBe(true);
    expect(posts()).toHaveLength(1);
  });
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove();
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
});
describe('T025 local pronunciation', () => {
  it('speaks the exact form with a positively local US voice and no requests', async () => {
    voices = [voice('en-US', false), voice('en-GB'), voice()];
    await mount(); await click();
    expect(spoken).toHaveLength(1);
    expect(spoken[0]).toMatchObject({ text: 'robust', lang: 'en-US', voice: voices[2] });
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(button().getAttribute('aria-label')).toBe('Dừng phát âm robust');
    await act(async () => spoken[0].onend?.());
    expect(button().getAttribute('aria-label')).toBe('Phát âm Mỹ robust');
  });
  it.each([{ voices: [] }, { voices: [voice('en-US', false)] }, { voices: [voice('en-GB')] }, { voices: [voice('en')] }])(
    'disables without a compatible local US voice: %j', async entry => {
      voices = entry.voices; await mount();
      expect(button().disabled).toBe(true);
      const description = document.getElementById(button().getAttribute('aria-describedby')!);
      expect(description?.textContent).toContain('Không có giọng en-US được xác nhận chạy cục bộ');
      await click(); expect(spoken).toEqual([]); expect(fetchSpy).not.toHaveBeenCalled();
    },
  );
  it('handles asynchronous enumeration and voice removal during playback', async () => {
    voices = []; await mount(); expect(button().disabled).toBe(true);
    voices = [voice()]; await act(async () => { events.dispatchEvent(new Event('voiceschanged')); });
    expect(button().disabled).toBe(false); await click();
    voices = [voice('en-US', false)];
    await act(async () => { events.dispatchEvent(new Event('voiceschanged')); });
    expect(cancel).toHaveBeenCalled(); expect(button().disabled).toBe(true);
  });
  it('bounds repeated clicks, ignores late completion, and cancels on navigation', async () => {
    await mount(); await click(); const lateEnd = spoken[0].onend; await click();
    expect(spoken).toHaveLength(1); expect(cancel).toHaveBeenCalled();
    await click();
    await act(async () => lateEnd?.());
    expect(button().getAttribute('aria-label')).toBe('Dừng phát âm robust');
    await mount(false); expect(cancel).toHaveBeenCalled(); expect(button().disabled).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
  it('cleans up on unmount and does not respond to later voice events', async () => {
    await mount(); await click(); await act(async () => root.render(null));
    expect(cancel).toHaveBeenCalled();
    await act(async () => { events.dispatchEvent(new Event('voiceschanged')); });
    expect(spoken).toHaveLength(1);
  });
  it('stops playback if the browser never signals completion', async () => {
    await mount(); await click();
    await act(async () => vi.advanceTimersByTime(15_000));
    expect(cancel).toHaveBeenCalled();
    expect(button().getAttribute('aria-label')).toBe('Phát âm Mỹ robust');
  });
  it('rechecks locality at click time even before voiceschanged arrives', async () => {
    await mount(); voices = [voice('en-US', false)]; await click();
    expect(button().disabled).toBe(true); expect(spoken).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
  it('interrupts the previous form and resets its control before playing another', async () => {
    await act(async () => root.render(<><AudioButton text="robust" /><AudioButton text="robustly" /></>));
    const buttons = container.querySelectorAll('button');
    await act(async () => buttons[0].click());
    await act(async () => buttons[1].click());
    expect(spoken.map(utterance => utterance.text)).toEqual(['robust', 'robustly']);
    expect(buttons[0].getAttribute('aria-label')).toBe('Phát âm Mỹ robust');
    expect(buttons[1].getAttribute('aria-label')).toBe('Dừng phát âm robustly');
  });
  it('handles unsupported browsers, empty text, and local synthesis failure', async () => {
    await mount(true, ''); expect(button().disabled).toBe(true);
    await mount();
    speechSynthesis.speak = () => { throw new Error('Synthetic failure'); };
    await click(); expect(container.textContent).toContain('Không phát âm được');
    vi.stubGlobal('speechSynthesis', undefined);
    await act(async () => root.render(null)); await mount();
    expect(button().disabled).toBe(true);
    expect(container.textContent).toContain('không hỗ trợ');
  });
});
