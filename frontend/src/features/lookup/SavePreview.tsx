import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ApiError, MutationUnknownError, apiClient, getETag } from '@/shared/api/client';
import { mapErrorToUIState } from '@/shared/api/errors';
import type { components, operations } from '@/shared/api/generated';

type Preview = components['schemas']['LookupResult'];
type Receipt = components['schemas']['SaveResult'];
type Source = components['schemas']['SourceFileView'];
type SourcePage = components['schemas']['SourceFilePage'];
type Operation = components['schemas']['Operation'];
type Request = components['schemas']['SaveWordFormsRequest'];
type Headers = operations['post_word_forms_api_v1_word_forms_post']['parameters']['header'];
type Form = Receipt['canonicalForms'][number];
type Intent = { request: Request; headers: Headers; formCount: number; operationId?: string };
type Phase = 'ready' | 'saving' | 'success' | 'failed' | 'unknown' | 'reconciling';
type SourceState = { date: string; kind: 'unread' | 'loading' | 'absent' | 'blocked' | 'error'; message: string } |
  { date: string; kind: 'existing'; source: Source; message: string };
type Outcome = { phase: Phase; message: string; receipt?: Receipt; error?: unknown; conflict?: components['schemas']['SourceConflictDetails'] };
type Props = {
  preview?: Preview;
  active?: boolean;
  onLockChange?: (locked: boolean) => void;
  onConfirmed?: (lookupId: string, receipt: Receipt) => void;
};

const storageKey = 'vocabulary.save-intent.v1';
const endpoint = '/api/v1/word-forms';
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const id = (value: unknown): value is string => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
const text = (value: unknown, max = Infinity): value is string => typeof value === 'string' && [...value].length <= max;
const revision = (value: unknown, min = 1): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= min;
const etag = (value: unknown): value is string => text(value, 128) && value.length > 0 && !/[\r\n\u0000]/u.test(value);
const verification = (value: unknown) => value === 'VERIFIED' || value === 'UNVERIFIED' || value === 'MISSING';
const list = (value: unknown, check: (entry: unknown) => boolean): value is unknown[] => Array.isArray(value) && value.every(check);
const unique = (values: string[]) => new Set(values).size === values.length;
const timestamp = (value: unknown): value is string => text(value, 80) && /T.*(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
function date(value: unknown): value is string {
  if (!text(value, 10) || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
function today(): string {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (type: string) => parts.find(entry => entry.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

function validIntent(value: unknown): value is Intent {
  if (!object(value) || !object(value.request) || !object(value.headers) ||
    !id(value.request.lookupId) || !date(value.request.noteDate) || !revision(value.formCount) || value.formCount > 100 ||
    !text(value.headers['Idempotency-Key'], 128) || !/^[\x20-\x7e]{1,128}$/.test(value.headers['Idempotency-Key']) ||
    (value.operationId !== undefined && !id(value.operationId))) return false;
  // Restore only the generated request/header fields, never arbitrary stored headers.
  if (Object.keys(value).some(key => !['request', 'headers', 'formCount', 'operationId'].includes(key)) ||
    Object.keys(value.request).some(key => !['lookupId', 'noteDate', 'sourceId', 'sourceRevision'].includes(key)) ||
    Object.keys(value.headers).some(key => !['Idempotency-Key', 'If-Match', 'If-None-Match'].includes(key))) return false;
  if (value.request.sourceId === undefined) return value.request.sourceRevision === undefined &&
    value.headers['If-Match'] === undefined && value.headers['If-None-Match'] === '*';
  return id(value.request.sourceId) && revision(value.request.sourceRevision) &&
    etag(value.headers['If-Match']) && value.headers['If-None-Match'] === undefined;
}
function loadIntent(): { intent: Intent | null; blocked: boolean } {
  if (typeof window === 'undefined') return { intent: null, blocked: false };
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw === null) return { intent: null, blocked: false };
    const value: unknown = JSON.parse(raw);
    return validIntent(value) ? { intent: value, blocked: false } : { intent: null, blocked: true };
  } catch { return { intent: null, blocked: true }; }
}
function persist(intent: Intent): boolean {
  try { sessionStorage.setItem(storageKey, JSON.stringify(intent)); return true; }
  catch { return false; }
}
function removeIntent(): boolean {
  try { sessionStorage.removeItem(storageKey); return true; }
  catch { return false; }
}
function validSource(value: unknown): value is Source {
  return object(value) && id(value.id) && date(value.noteDate) && revision(value.revision, 0) &&
    etag(value.etag) && text(value.relativePath) && ['VALID', 'INVALID', 'MISSING'].includes(String(value.status)) &&
    (value.status !== 'VALID' || value.revision >= 1);
}
function validSourcePage(value: unknown, selected: string): value is SourcePage {
  return object(value) && list(value.data, validSource) && value.data.length <= 100 && value.data.every(entry => validSource(entry) && entry.noteDate === selected) &&
    object(value.pagination) && value.pagination.hasMore === false && value.pagination.nextCursor === null &&
    revision(value.pagination.pageSize) && value.pagination.pageSize <= 100;
}
function validForm(value: unknown): value is Form {
  const meaning = (entry: unknown, language: string) => object(entry) && entry.language === language && text(entry.text) && verification(entry.verificationStatus);
  return object(value) && id(value.id) && id(value.familyId) && revision(value.revision) && text(value.lemma) &&
    text(value.partOfSpeech) && verification(value.verificationSummary) && timestamp(value.updatedAt) &&
    (value.ipaUs === null || text(value.ipaUs)) && (value.cambridgeUrl === null || text(value.cambridgeUrl)) &&
    list(value.meaningsEn, entry => meaning(entry, 'en')) && list(value.meaningsVi, entry => meaning(entry, 'vi')) &&
    list(value.examples, entry => object(entry) && text(entry.english) && text(entry.vietnamese) && verification(entry.verificationStatus)) &&
    list(value.sourceRefs, entry => object(entry) && id(entry.sourceId) && date(entry.noteDate) && ['VALID', 'INVALID', 'MISSING'].includes(String(entry.status))) &&
    (value.card === null || (object(value.card) && id(value.card.id) && text(value.card.state, 32) &&
      (value.card.dueAt === null || timestamp(value.card.dueAt))));
}
function validReceipt(value: unknown, intent: Intent): value is Receipt {
  if (!object(value) || value.markdownSync !== 'COMPLETED' || !id(value.operationId) ||
    (intent.operationId !== undefined && value.operationId !== intent.operationId) || value.noteDate !== intent.request.noteDate ||
    !id(value.sourceId) || !revision(value.sourceRevision) || !etag(value.sourceEtag) ||
    (getETag(value) !== undefined && getETag(value) !== value.sourceEtag) ||
    (intent.request.sourceId !== undefined && (!revision(intent.request.sourceRevision) || value.sourceId !== intent.request.sourceId || value.sourceRevision !== intent.request.sourceRevision + 1)) ||
    (intent.request.sourceId === undefined && value.sourceRevision !== 1) ||
    !list(value.savedForms, entry => object(entry) && id(entry.id) && revision(entry.revision)) ||
    !list(value.canonicalForms, validForm) || !list(value.createdCardIds, id) || !list(value.reusedCardIds, id)) return false;
  const forms = value.canonicalForms as Form[];
  const saved = value.savedForms as Receipt['savedForms'];
  const cards = [...value.createdCardIds, ...value.reusedCardIds] as string[];
  if (forms.length !== intent.formCount || saved.length !== forms.length || !unique(forms.map(form => form.id)) ||
    !unique(saved.map(form => form.id)) || !unique(cards) || cards.length !== forms.length ||
    !forms.every(form => saved.some(entry => entry.id === form.id && entry.revision === form.revision) &&
      form.sourceRefs.some(ref => ref.sourceId === value.sourceId && ref.noteDate === value.noteDate && ref.status === 'VALID') &&
      form.card !== null && cards.includes(form.card.id)) || !unique(forms.map(form => form.card?.id ?? ''))) return false;
  // The request's lookupId binds the preview. Reused canonical forms may retain
  // an older display lemma; do not duplicate backend identity normalization here.
  return true;
}
function validOperation(value: unknown, operationId: string): value is Operation {
  return object(value) && value.operationId === operationId && value.kind === 'SAVE' &&
    ['PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN'].includes(String(value.status)) && timestamp(value.createdAt) && timestamp(value.updatedAt) &&
    (value.resultRef === undefined || value.resultRef === null || id(value.resultRef)) &&
    (value.status !== 'SUCCEEDED' || value.resultRef === operationId);
}
function conflictDetails(error: ApiError, intent: Intent): components['schemas']['SourceConflictDetails'] | undefined {
  const details = error.details;
  return details?.kind === 'CONFLICT' && details.resourceType === 'SOURCE' && details.resourceId === intent.request.sourceId &&
    details.expectedRevision === intent.request.sourceRevision && revision(details.expectedRevision) && revision(details.currentRevision) ? details : undefined;
}
function recoveryError(error: unknown): unknown {
  if (!(error instanceof ApiError)) return error instanceof MutationUnknownError ? error : new Error('Không đọc được API cục bộ.');
  // Shared recovery presentation receives redacted text, never a raw backend message.
  return new ApiError(error.status, { code: error.code, requestId: id(error.requestId) ? error.requestId : 'req_unknown', message: 'Yêu cầu lưu chưa hoàn tất.' });
}

function VocabularyContent({ forms }: { forms: Preview['forms'] | Receipt['canonicalForms'] }) {
  return <ul className="space-y-4 pl-5" aria-label="Nội dung từ vựng">
    {forms.map(form => <li key={'formId' in form ? form.formId : form.id}>
      <p className="m-0 font-medium"><span lang="en">{form.lemma}</span> · {form.partOfSpeech} · {form.verificationSummary}</p>
      <p>IPA Mỹ: {form.ipaUs ?? 'MISSING'}{'ipaStatus' in form ? ` · ${form.ipaStatus}` : ''}</p>
      {form.meaningsEn.map((meaning, index) => <p key={`en-${index}`} lang="en" className="m-0 whitespace-pre-wrap">{meaning.text} · {meaning.verificationStatus}</p>)}
      {form.meaningsVi.map((meaning, index) => <p key={`vi-${index}`} lang="vi" className="m-0 whitespace-pre-wrap">{meaning.text} · {meaning.verificationStatus}</p>)}
      {form.examples.map((example, index) => <div key={index}><p lang="en" className="m-0 whitespace-pre-wrap">{example.english}</p><p lang="vi" className="m-0 whitespace-pre-wrap">{example.vietnamese} · {example.verificationStatus}</p></div>)}
      <p>Cambridge: {form.cambridgeUrl ?? 'MISSING'}{'cambridgeStatus' in form ? ` · ${form.cambridgeStatus}` : ''}</p>
      {'card' in form && form.card && <p>Trạng thái thẻ: {form.card.state}. Lịch đến hạn: {form.card.dueAt ?? 'Chưa có'}.</p>}
    </li>)}
  </ul>;
}

export function SavePreview({ preview, active = true, onLockChange, onConfirmed }: Props) {
  const [boot] = useState(loadIntent);
  const [selected, setSelected] = useState(() => boot.intent?.request.noteDate ?? today());
  const [intent, setIntent] = useState<Intent | null>(boot.intent);
  const [source, setSource] = useState<SourceState>({ date: '', kind: 'unread', message: 'Đọc nguồn ngày đã chọn trước khi lưu.' });
  const [outcome, setOutcome] = useState<Outcome>(() => ({ phase: boot.intent || boot.blocked ? 'unknown' : 'ready',
    message: boot.blocked ? 'Chưa xác định kết quả lưu. Không đọc được định danh thao tác đã giữ; chưa cho phép lưu mới.' :
      boot.intent ? 'Chưa xác định kết quả lưu trước đó. Bấm Kiểm tra kết quả lưu để đối soát.' : 'Chọn ngày và đọc nguồn trước khi lưu.' }));
  const [confirmed, setConfirmed] = useState<Record<string, { intent: Intent; receipt: Receipt }>>({});
  const alive = useRef(true);
  const visible = useRef(active);
  const dispatching = useRef(false);
  const pendingIntent = useRef<Intent | null>(boot.intent);
  const readVersion = useRef(0);
  const previewIdentity = useRef(preview?.lookupId);
  const readController = useRef<AbortController | null>(null);
  const operationController = useRef<AbortController | null>(null);
  const status = useRef<HTMLParagraphElement>(null);
  const statusId = useId();
  const inputId = useId();
  const busy = outcome.phase === 'saving' || outcome.phase === 'reconciling';
  const locked = busy || outcome.phase === 'unknown';
  const confirmationKey = `${preview?.lookupId ?? intent?.request.lookupId}:${selected}`;
  const confirmation = confirmed[confirmationKey];
  useEffect(() => { onLockChange?.(locked); }, [locked, onLockChange]);
  useEffect(() => {
    visible.current = active;
    if (!active) {
      readVersion.current += 1; readController.current?.abort(); operationController.current?.abort();
      setSource(previous => previous.kind === 'loading' ? { date: previous.date, kind: 'unread', message: 'Đọc lại nguồn khi quay lại trang.' } : previous);
    }
  }, [active]);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; readVersion.current += 1; readController.current?.abort(); operationController.current?.abort(); };
  }, []);
  useEffect(() => {
    if (active && ['success', 'failed', 'unknown'].includes(outcome.phase) && !document.activeElement?.closest('[role="dialog"]')) status.current?.focus();
  }, [outcome, active]);
  useEffect(() => {
    if (previewIdentity.current === preview?.lookupId) return;
    previewIdentity.current = preview?.lookupId;
    if (locked) return;
    readVersion.current += 1; readController.current?.abort();
    setSource({ date: '', kind: 'unread', message: 'Đọc nguồn ngày đã chọn trước khi lưu.' });
    setIntent(null);
    setOutcome({ phase: 'ready', message: 'Chọn ngày và đọc nguồn cho bản xem trước này trước khi lưu.' });
  }, [preview?.lookupId, locked]);

  const show = (next: Outcome) => { if (alive.current) setOutcome(next); };
  const hold = (current: Intent, message: string, error?: unknown) => {
    pendingIntent.current = current;
    persist(current);
    setIntent(current);
    show({ phase: 'unknown', message, error: error ? recoveryError(error) : undefined });
  };
  const fail = (current: Intent, message: string, error?: unknown, conflict?: components['schemas']['SourceConflictDetails']) => {
    pendingIntent.current = null; setIntent(null); removeIntent();
    setSource({ date: current.request.noteDate, kind: 'unread', message: 'Đọc lại nguồn trước khi bắt đầu thao tác mới.' });
    show({ phase: 'failed', message, error: error ? recoveryError(error) : undefined, conflict });
  };
  const readSource = useCallback(async (noteDate: string, afterConfirmation = false) => {
    if (!date(noteDate) || !visible.current || (dispatching.current && !afterConfirmation) || pendingIntent.current || boot.blocked) return;
    readController.current?.abort();
    const version = ++readVersion.current;
    const controller = new AbortController(); readController.current = controller;
    const timer = setTimeout(() => controller.abort(), 15_000);
    setSource({ date: noteDate, kind: 'loading', message: 'Đang đọc nguồn ngày đã chọn.' });
    try {
      const page = await apiClient<SourcePage>('/api/v1/sources', { params: { noteDate, pageSize: '100', sortBy: 'noteDate', sortOrder: 'asc' }, cache: 'no-store', signal: controller.signal });
      if (!alive.current || version !== readVersion.current) return;
      if (!validSourcePage(page, noteDate)) setSource({ date: noteDate, kind: 'error', message: 'Không xác nhận được toàn bộ nguồn của ngày đã chọn. Chưa cho phép lưu.' });
      else if (page.data.length === 0) setSource({ date: noteDate, kind: 'absent', message: 'Ngày này chưa có nguồn. Có thể lưu toàn bộ bản xem trước.' });
      else if (page.data.length === 1 && page.data[0].status === 'VALID') setSource({ date: noteDate, kind: 'existing', source: page.data[0], message: `Nguồn hợp lệ, revision ${page.data[0].revision}.` });
      else setSource({ date: noteDate, kind: 'blocked', message: page.data.length > 1 ? 'Có nhiều nguồn cho ngày này. Cần xử lý nguồn trước khi lưu.' : `Nguồn ${page.data[0].status}. Cần sửa nguồn trước khi lưu.` });
    } catch {
      if (alive.current && version === readVersion.current) setSource({ date: noteDate, kind: 'error', message: 'Không đọc được nguồn. Bạn có thể đọc lại; chưa cho phép lưu.' });
    } finally { clearTimeout(timer); if (readController.current === controller) readController.current = null; }
  }, [boot.blocked]);

  // The caller holds the dispatch guard across operation GET and receipt replay.
  const send = async (current: Intent, replay: boolean) => {
    pendingIntent.current = current; setIntent(current);
    show({ phase: replay ? 'reconciling' : 'saving', message: replay ? 'Đang lấy biên nhận của cùng thao tác.' : 'Đang lưu. Chưa xác nhận Markdown hoặc thẻ.' });
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 30_000);
    try {
      // The generated header contract allows nullable If-Match. Valid intents
      // omit it for creation; pass only the actual conditional header to HTTP.
      const headers: Record<string, string> = { 'Idempotency-Key': current.headers['Idempotency-Key'] };
      if (typeof current.headers['If-Match'] === 'string') headers['If-Match'] = current.headers['If-Match'];
      if (current.headers['If-None-Match'] === '*') headers['If-None-Match'] = '*';
      const value = await apiClient<Receipt>(endpoint, { method: 'POST', body: JSON.stringify(current.request), headers, signal: controller.signal });
      if (!alive.current) return;
      if (!validReceipt(value, current)) { hold(current, 'Chưa xác định kết quả lưu. Phản hồi không phải biên nhận đầy đủ của thao tác này.'); return; }
      const settled: Intent = { ...current, operationId: value.operationId };
      persist(settled); pendingIntent.current = null; setIntent(settled);
      setConfirmed(previous => ({ ...previous, [`${current.request.lookupId}:${current.request.noteDate}`]: { intent: settled, receipt: value } }));
      show({ phase: 'success', receipt: value, message: `Đã lưu để ôn ngày ${value.noteDate}. Markdown đã hoàn tất theo biên nhận Backend.` });
      onConfirmed?.(current.request.lookupId, value);
      // Source reads use no-store. There is no shared query cache in this slice.
      if (visible.current) void readSource(current.request.noteDate, true);
    } catch (error) {
      if (!alive.current) return;
      if (!(error instanceof ApiError)) {
        hold(current, 'Chưa xác định kết quả lưu. Kiểm tra cùng thao tác trước khi lưu mới.', error); return;
      }
      const code = text(error.code, 80) && /^[A-Z][A-Z0-9_]*$/.test(error.code) ? error.code : 'INTERNAL_ERROR';
      const details = error.details;
      if (details?.kind === 'RETRY' && details.operationId !== undefined) {
        if (!id(details.operationId) || (details.operationKind !== undefined && details.operationKind !== 'SAVE') ||
          (current.operationId !== undefined && current.operationId !== details.operationId)) {
          hold(current, 'Chưa xác định kết quả lưu. Định danh thao tác trong phản hồi không khớp.'); return;
        }
        current = { ...current, operationId: details.operationId };
      }
      // A replay may be rejected before the ledger is reached. It cannot settle an old unknown intent.
      if (replay || code === 'IDEMPOTENCY_IN_FLIGHT' || error.status >= 500 ||
        (current.operationId !== undefined && !['REVISION_CONFLICT', 'SOURCE_MISSING', 'SOURCE_NOT_WRITABLE'].includes(code)) || details?.kind === 'RESTORE') {
        hold(current, `Chưa xác định kết quả lưu (${code}). Kiểm tra biên nhận; chưa tạo thao tác mới.`, error); return;
      }
      const message = code === 'REVISION_CONFLICT' ? 'REVISION_CONFLICT: Nguồn đã thay đổi. Giữ bản xem trước, đọc lại nguồn rồi bấm Lưu khi bạn muốn.' :
        code === 'VALIDATION_ERROR' ? 'VALIDATION_ERROR: Nội dung hoặc ngày không được Backend chấp nhận. Kiểm tra ngày học hoặc tra cứu lại để tạo bản xem trước mới; bản xem trước hiện tại được giữ.' :
          code.startsWith('SESSION_') ? `${code}: Mở lại ứng dụng qua launcher để khôi phục phiên. Bản xem trước được giữ.` :
            code === 'AI_CONSENT_REQUIRED' || code === 'AI_POLICY_CHANGED' ? `${code}: Lưu bản xem trước không gửi AI. Kiểm tra quyền và trạng thái API trước khi thử lại.` :
              `${code}: Backend từ chối lưu. Kiểm tra nguồn và trạng thái ứng dụng trước khi thử lại.`;
      fail(current, message, error, conflictDetails(error, current));
    } finally { clearTimeout(timer); }
  };
  const save = async () => {
    if (!active || dispatching.current || locked || boot.blocked || !preview || preview.status !== 'PREVIEW' || preview.forms.length === 0 ||
      !date(selected) || source.date !== selected || !['absent', 'existing'].includes(source.kind)) return;
    const existing = confirmed[`${preview.lookupId}:${selected}`];
    const request: Request = source.kind === 'existing'
      ? { lookupId: preview.lookupId, noteDate: selected, sourceId: source.source.id, sourceRevision: source.source.revision }
      : { lookupId: preview.lookupId, noteDate: selected };
    const key = crypto.randomUUID();
    const headers: Headers = source.kind === 'existing' ? { 'Idempotency-Key': key, 'If-Match': source.source.etag } : { 'Idempotency-Key': key, 'If-None-Match': '*' };
    const current: Intent = existing?.intent ?? { request, headers, formCount: preview.forms.length };
    if (!persist(current)) { show({ phase: 'failed', message: 'Không giữ được định danh lưu qua tải lại. Chưa gửi yêu cầu; kiểm tra bộ nhớ trình duyệt rồi thử lại.' }); return; }
    dispatching.current = true;
    onLockChange?.(true);
    try { await send(current, !!existing); } finally { dispatching.current = false; }
  };
  const reconcile = async (current = intent) => {
    if (!current || !active || dispatching.current || boot.blocked) return;
    if (!persist(current)) {
      hold(current, 'Chưa xác định kết quả đối soát. Không giữ được định danh qua tải lại; chưa gửi lại yêu cầu.'); return;
    }
    pendingIntent.current = current; setIntent(current);
    dispatching.current = true;
    onLockChange?.(true);
    show({ phase: 'reconciling', message: 'Đang kiểm tra cùng thao tác lưu. Chưa xác nhận thành công.' });
    try {
      if (current.operationId !== undefined) {
        const controller = new AbortController(); operationController.current = controller;
        const timer = setTimeout(() => controller.abort(), 15_000);
        let operation: Operation;
        try { operation = await apiClient<Operation>(`/api/v1/operations/${encodeURIComponent(current.operationId)}`, { cache: 'no-store', signal: controller.signal }); }
        finally { clearTimeout(timer); if (operationController.current === controller) operationController.current = null; }
        if (!alive.current) return;
        if (!validOperation(operation, current.operationId)) { hold(current, 'Chưa xác định kết quả lưu. Biên nhận thao tác không hợp lệ.'); return; }
        if (operation.status === 'FAILED') { fail(current, 'Backend xác nhận thao tác đã thất bại. Đọc lại nguồn rồi bấm Lưu để bắt đầu thao tác mới.'); return; }
        if (operation.status !== 'SUCCEEDED') { hold(current, operation.status === 'PENDING' ? 'Chưa xác định: thao tác đang xử lý. Chỉ kiểm tra lại; chưa gửi lại.' : 'Chưa xác định: Backend giữ trạng thái UNKNOWN. Chỉ kiểm tra lại; chưa gửi lại.'); return; }
      }
      if (visible.current) await send(current, true);
      else hold(current, 'Chưa xác định kết quả lưu. Quay lại trang để lấy biên nhận.');
    } catch (error) { if (alive.current) hold(current, 'Chưa xác định kết quả lưu. Không đọc được biên nhận; định danh cũ được giữ.', error); }
    finally { dispatching.current = false; }
  };
  const reloadSource = () => { if (!locked && date(selected)) void readSource(selected); };
  const effectiveReceipt = !locked && confirmation ? confirmation.receipt :
    outcome.phase === 'success' && outcome.receipt?.noteDate === selected && (!preview || preview.lookupId === intent?.request.lookupId) ? outcome.receipt : undefined;
  const recovery = outcome.error ? mapErrorToUIState(outcome.error) : undefined;
  const canSave = active && !!preview && preview.status === 'PREVIEW' && preview.forms.length > 0 && !locked && !boot.blocked && date(selected) &&
    source.date === selected && (source.kind === 'absent' || source.kind === 'existing') && !confirmation;
  if (!preview && !intent && !boot.blocked && !outcome.receipt) return null;
  return <Card role="region" aria-label="Lưu bản xem trước để ôn tập" hidden={!active} className="min-w-0 break-words [overflow-wrap:anywhere]">
    <CardHeader><CardTitle><h2 className="m-0 text-xl">Lưu bản xem trước</h2></CardTitle></CardHeader>
    <CardContent className="space-y-4 min-w-0">
      {preview && <><p>Lưu tất cả dạng từ của <strong>{preview.term}</strong>. Nội dung và nhãn xác minh được giữ trong bản xem trước.</p><VocabularyContent forms={preview.forms} /></>}
      {!preview && intent && <p>Đang khôi phục biên nhận cho bản xem trước {intent.request.lookupId}. Nội dung sẽ hiển thị khi Backend xác nhận.</p>}
      <label htmlFor={inputId} className="block font-medium">Ngày học</label>
      <input id={inputId} type="date" value={selected} required disabled={locked || boot.blocked} aria-invalid={!date(selected)} aria-describedby={statusId}
        className="min-h-11 max-w-full rounded-md border border-input bg-background px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        onChange={event => {
          if (locked || dispatching.current) return;
          readVersion.current += 1; readController.current?.abort();
          setSelected(event.target.value); setSource({ date: '', kind: 'unread', message: 'Đọc nguồn ngày đã chọn trước khi lưu.' });
          show({ phase: 'ready', message: 'Ngày đã thay đổi. Đọc nguồn trước khi lưu; chưa gửi yêu cầu.' });
        }} />
      <p id={statusId} ref={status} tabIndex={-1} role={outcome.phase === 'failed' ? 'alert' : 'status'} aria-live={outcome.phase === 'failed' ? 'assertive' : 'polite'} aria-atomic="true"
        className="rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{outcome.message}</p>
      {!date(selected) && <p role="alert">Chọn ngày hợp lệ theo định dạng YYYY-MM-DD.</p>}
      <p role="status" aria-live="polite">{source.date === selected || source.kind === 'unread' ? source.message : 'Đọc nguồn ngày đã chọn trước khi lưu.'}</p>
      {source.date === selected && source.kind === 'existing' && <p>Nguồn: {source.source.id}. Revision: {source.source.revision}.</p>}
      {outcome.conflict && <p role="alert">Nguồn {outcome.conflict.resourceId}: revision trong yêu cầu {outcome.conflict.expectedRevision}, revision hiện tại {outcome.conflict.currentRevision}.</p>}
      {recovery && <div role="alert"><p>{recovery.title}. {recovery.message}</p>{recovery.requestId && <p>Mã yêu cầu: {recovery.requestId}</p>}
        {recovery.actionType === 'REBOOTSTRAP' && <p>Mở lại ứng dụng từ launcher, giữ định danh thao tác để kiểm tra kết quả.</p>}
        {recovery.actionType === 'UPDATE_CONSENT' && <a href="/status#ai-consent" className="underline text-primary">Xem quyền AI</a>}</div>}
      {intent?.operationId && <p>Mã thao tác lưu: {intent.operationId}</p>}
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="outline" className="min-h-11" disabled={!active || locked || boot.blocked || !date(selected) || source.kind === 'loading'} onClick={reloadSource}>
          {outcome.phase === 'failed' ? 'Đọc lại nguồn' : 'Đọc nguồn'}</Button>
        <Button type="button" className="min-h-11" disabled={!canSave} onClick={() => void save()} aria-describedby={statusId}>
          {outcome.phase === 'saving' ? 'Đang lưu…' : confirmation ? 'Đã lưu ngày này' : 'Lưu để ôn'}</Button>
        {outcome.phase === 'unknown' && intent && <Button type="button" variant="outline" className="min-h-11" disabled={!active || busy} onClick={() => void reconcile()}>Kiểm tra kết quả lưu</Button>}
        {effectiveReceipt && confirmation && <Button type="button" variant="outline" className="min-h-11" disabled={!active || busy} onClick={() => void reconcile(confirmation.intent)}>Kiểm tra biên nhận</Button>}
      </div>
      {busy && <p aria-busy="true">Đang chờ Backend. Chưa có xác nhận mới.</p>}
      {effectiveReceipt && <section aria-label="Biên nhận lưu" className="space-y-3">
        <p>Đã lưu để ôn ngày {effectiveReceipt.noteDate}. Biên nhận: {effectiveReceipt.operationId}.</p>
        <p>Markdown: {effectiveReceipt.markdownSync}. Nguồn: {effectiveReceipt.sourceId}. Revision: {effectiveReceipt.sourceRevision}. ETag: {effectiveReceipt.sourceEtag}.</p>
        <p>Thẻ mới: {effectiveReceipt.createdCardIds.length}. Thẻ dùng lại: {effectiveReceipt.reusedCardIds.length}.</p>
        <p>Thẻ dùng lại giữ định danh. Nếu nội dung học thay đổi, Backend đặt lại lịch; trạng thái và lịch dưới đây là kết quả đã xác nhận.</p>
        <VocabularyContent forms={effectiveReceipt.canonicalForms} />
      </section>}
    </CardContent>
  </Card>;
}
