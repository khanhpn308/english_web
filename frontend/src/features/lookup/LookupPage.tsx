import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAiConsent } from '@/features/consent/AiConsentGate';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';
import { LookupResult } from './LookupResult';
import { AudioButton } from './AudioButton';
import { SavePreview } from './SavePreview';

type Preview = components['schemas']['LookupResult'];
type Operation = components['schemas']['Operation'];
type Intent = { key: string; requestId: string; term: string; edit: number; operationId?: string };
type Phase = 'idle' | 'validation' | 'authorizing' | 'loading' | 'success' | 'empty' | 'recoverable' | 'terminal' | 'unknown' | 'reconciling';
type View = { phase: Phase; message: string; preview?: Preview; requestId?: string; code?: string };
const endpoint = '/api/v1/lookups';
const busyPhases: Phase[] = ['authorizing', 'loading', 'reconciling'];
const statuses = ['VERIFIED', 'UNVERIFIED', 'MISSING'];
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 4096): value is string => typeof value === 'string' && value.trim().length > 0 && [...value].length <= max;
const nullableText = (value: unknown) => value === null || text(value);
const verified = (value: unknown) => typeof value === 'string' && statuses.includes(value);
const list = (value: unknown, check: (entry: unknown) => boolean): boolean => Array.isArray(value) && value.length <= 100 && value.every(check);
const date = (value: unknown) => text(value, 80) && /T.*(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
const identifier = (value: unknown): value is string => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value);

// Generated DTOs describe compile-time types; the client does not validate response JSON.
function validPreview(value: unknown): value is Preview {
  if (!record(value)) return false;
  const meaning = (entry: unknown, language: string) => record(entry) && entry.language === language && text(entry.text) && verified(entry.verificationStatus);
  const form = (entry: unknown) => record(entry) && identifier(entry.formId) && text(entry.lemma, 128) && text(entry.partOfSpeech, 32) &&
    list(entry.meaningsEn, item => meaning(item, 'en')) && list(entry.meaningsVi, item => meaning(item, 'vi')) &&
    list(entry.examples, item => record(item) && text(item.english) && text(item.vietnamese) && verified(item.verificationStatus)) &&
    nullableText(entry.ipaUs) && nullableText(entry.cambridgeUrl) && verified(entry.ipaStatus) && verified(entry.cambridgeStatus) && verified(entry.verificationSummary) &&
    (entry.ipaUs !== null || entry.ipaStatus === 'MISSING') && (entry.cambridgeUrl !== null || entry.cambridgeStatus === 'MISSING');
  return identifier(value.lookupId) && identifier(value.operationId) && typeof value.term === 'string' && normalizedTerm(value.term) === value.term &&
    text(value.provider, 128) && text(value.model, 128) && text(value.promptVersion, 128) && date(value.createdAt) &&
    verified(value.verificationSummary) && typeof value.status === 'string' && ['PREVIEW', 'FAILED'].includes(value.status) && list(value.forms, form) &&
    new Set((value.forms as Preview['forms']).map(entry => entry.formId)).size === (value.forms as Preview['forms']).length;
}
function validOperation(value: unknown, id: string): value is Operation {
  return record(value) && value.operationId === id && value.kind === 'LOOKUP' &&
    typeof value.status === 'string' && ['PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN'].includes(value.status) && date(value.createdAt) && date(value.updatedAt) &&
    (value.resultRef === undefined || nullableText(value.resultRef)) && (value.errorCategory === undefined || nullableText(value.errorCategory));
}
function normalizedTerm(raw: string): string | null {
  const nfc = raw.normalize('NFC');
  if (/[\u0000-\u0008\u000e-\u001f\u007f-\u009f\ud800-\udfff]/u.test(nfc)) return null;
  // Match Python str.split whitespace, after the contract's control-character rejection.
  const normalized = nfc.split(/[ \t\n\r\v\f\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u).filter(Boolean).join(' ');
  return [...normalized].length >= 1 && [...normalized].length <= 80 ? normalized : null;
}

export function LookupPage({ active = true }: { active?: boolean }) {
  const consent = useAiConsent();
  const [term, setTerm] = useState('');
  const [view, setView] = useState<View>({ phase: 'idle', message: 'Nhập từ hoặc cụm từ để tra cứu.' });
  const [saveLocked, setSaveLocked] = useState(false);
  const [saved, setSaved] = useState<{ lookupId: string; noteDate: string } | null>(null);
  const saveLock = useRef(false);
  const updateSaveLock = useCallback((locked: boolean) => { saveLock.current = locked; setSaveLocked(locked); }, []);
  const confirmSave = useCallback((lookupId: string, receipt: components['schemas']['SaveResult']) => {
    setSaved({ lookupId, noteDate: receipt.noteDate });
    setView(current => current.preview?.lookupId === lookupId ? {
      ...current, message: `Backend đã xác nhận lưu bản xem trước vào ngày ${receipt.noteDate}.`,
    } : current);
  }, []);
  const input = useRef<HTMLInputElement>(null);
  const status = useRef<HTMLParagraphElement>(null);
  const alive = useRef(true);
  const visible = useRef(active);
  const busy = useRef(false);
  const editVersion = useRef(0);
  const actionVersion = useRef(0);
  const intent = useRef<Intent | null>(null);
  const read = useRef<AbortController | null>(null);
  const post = useRef<AbortController | null>(null);

  useEffect(() => {
    visible.current = active;
    if (!active) { actionVersion.current += 1; read.current?.abort(); }
  }, [active]);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; actionVersion.current += 1; read.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!visible.current || busyPhases.includes(view.phase) || view.phase === 'idle') return;
    if (document.activeElement?.closest('[role="dialog"]')) return;
    if (view.phase === 'validation') input.current?.focus();
    else status.current?.focus();
  }, [view]);

  const show = (next: View) => { if (alive.current) setView(next); };
  const unknown = (activeIntent: Intent, message = 'Chưa xác định kết quả thao tác. Kiểm tra kết quả trước khi tra cứu mới.') => {
    intent.current = activeIntent;
    show({ phase: 'unknown', message, requestId: activeIntent.requestId });
  };
  const complete = (data: Preview, activeIntent: Intent) => {
    intent.current = null;
    if (activeIntent.edit !== editVersion.current) {
      show({ phase: 'idle', message: 'Thao tác trước đã kết thúc. Nội dung nhập đã thay đổi; hãy bấm Tra cứu để gửi từ hiện tại.' });
    } else if (data.status === 'FAILED') {
      show({ phase: 'terminal', message: 'Thao tác đã thất bại. Bạn có thể chủ động thử lại.', requestId: activeIntent.requestId });
    } else {
      show({ phase: data.forms.length ? 'success' : 'empty', preview: data,
        message: data.forms.length ? 'Đã có kết quả xem trước. Chưa lưu từ hoặc tạo thẻ.' : 'Không có dạng từ trong kết quả xem trước.' });
    }
  };
  const send = async (activeIntent: Intent, replay = false) => {
    intent.current = activeIntent;
    show({ phase: 'loading', message: 'Đang tra cứu. Bạn có thể sửa từ; kết quả cũ sẽ không thay nội dung mới.' });
    const controller = new AbortController();
    post.current = controller;
    const timer = setTimeout(() => controller.abort(), 120_000);
    try {
      const data = await apiClient<Preview>(endpoint, {
        method: 'POST', body: JSON.stringify({ term: activeIntent.term } satisfies components['schemas']['LookupRequest']),
        headers: { 'Idempotency-Key': activeIntent.key, 'X-Request-ID': activeIntent.requestId }, signal: controller.signal,
      });
      if (!alive.current) return;
      if (!validPreview(data) || data.term !== activeIntent.term || (activeIntent.operationId && data.operationId !== activeIntent.operationId)) {
        unknown(activeIntent, 'Chưa xác định kết quả: phản hồi không hợp lệ. Kiểm tra cùng thao tác, không tạo yêu cầu mới.'); return;
      }
      activeIntent.operationId = data.operationId;
      complete(data, activeIntent);
    } catch (failure) {
      if (!alive.current) return;
      if (failure instanceof ApiError) {
        const code = typeof failure.code === 'string' && /^[A-Z][A-Z0-9_]{0,79}$/.test(failure.code) ? failure.code : 'INTERNAL_ERROR';
        const operationId = failure.details?.kind === 'RETRY' ? failure.details.operationId : undefined;
        if (activeIntent.operationId && operationId && operationId !== activeIntent.operationId) {
          unknown(activeIntent, 'Chưa xác định kết quả: mã thao tác trong phản hồi không khớp.'); return;
        }
        if (identifier(operationId)) activeIntent.operationId = operationId;
        const requestId = identifier(failure.requestId) ? failure.requestId : activeIntent.requestId;
        // These two T008 errors are persisted terminal failures, including replay.
        // Session/configuration rejection can precede the ledger and cannot settle
        // a previously uncertain intent.
        if (replay && ['BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE'].includes(code)) {
          intent.current = null;
          show({ phase: 'terminal', message: 'Thao tác đã thất bại. Bấm Thử lại để bắt đầu thao tác mới.', code, requestId });
        } else if (replay || activeIntent.operationId || code === 'IDEMPOTENCY_IN_FLIGHT') {
          show({ phase: 'unknown', message: 'Chưa xác định kết quả thao tác. Kiểm tra kết quả trước khi tra cứu mới.', code, requestId });
        } else if (['AI_CONSENT_REQUIRED', 'VALIDATION_ERROR', 'CONFIGURATION_REQUIRED', 'BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE', 'NETWORK_REQUIRED', 'SESSION_REQUIRED', 'SESSION_INVALID', 'ORIGIN_FORBIDDEN'].includes(code) || failure.status < 500) {
          intent.current = null;
          show({ phase: code === 'AI_CONSENT_REQUIRED' ? 'recoverable' : 'terminal', code, requestId,
            message: code === 'AI_CONSENT_REQUIRED' ? 'Quyền AI đã thay đổi. Đọc lại quyền; sau đó bấm Tra cứu khi bạn muốn gửi.' :
              code.startsWith('SESSION_') ? 'Phiên làm việc không còn hợp lệ. Mở lại ứng dụng từ launcher; từ đang nhập vẫn được giữ trên màn hình.' :
                'Không tra cứu được. Kiểm tra trạng thái API và bridge trước khi chủ động thử lại.' });
          if (code === 'AI_CONSENT_REQUIRED') void consent.refresh();
        } else unknown(activeIntent);
      } else {
        if (failure instanceof MutationUnknownError && identifier(failure.operationId)) activeIntent.operationId = failure.operationId;
        unknown(activeIntent);
      }
    } finally { clearTimeout(timer); post.current = null; }
  };

  const authorize = async (dispatch: () => Promise<void>) => {
    const version = actionVersion.current;
    let authorized = false;
    await consent.requestPermission(() => { authorized = version === actionVersion.current && alive.current && visible.current; });
    if (authorized) await dispatch();
    else if (alive.current) show({ phase: intent.current ? 'unknown' : version !== actionVersion.current ? 'idle' : 'recoverable',
      message: intent.current ? 'Chưa xác định kết quả thao tác cũ. Chưa gửi lại; sau khi chọn quyền AI, hãy bấm Kiểm tra kết quả khi bạn muốn tiếp tục.' :
        'Chưa gửi yêu cầu tra cứu. Từ đang nhập được giữ lại. Sau khi chọn quyền AI, hãy bấm lại thao tác khi bạn muốn gửi.' });
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy.current || intent.current || saveLock.current || !visible.current) return;
    const normalized = normalizedTerm(term);
    if (!normalized) { show({ phase: 'validation', message: 'Nhập từ có 1–80 ký tự Unicode sau chuẩn hóa, không có ký tự điều khiển.' }); return; }
    busy.current = true;
    const edit = editVersion.current;
    show({ phase: 'authorizing', message: 'Đang kiểm tra quyền AI. Chưa gửi từ để tra cứu.' });
    try {
      await authorize(async () => {
        await send({ term: normalized, edit, key: crypto.randomUUID(), requestId: `req_${crypto.randomUUID()}` });
      });
    } catch { show({ phase: 'recoverable', message: 'Không đọc được quyền AI. Kiểm tra API cục bộ rồi bấm lại; từ đang nhập được giữ lại.' }); }
    finally { busy.current = false; }
  };
  const reconcile = async () => {
    const activeIntent = intent.current;
    if (!activeIntent || busy.current || !visible.current) return;
    busy.current = true;
    show({ phase: 'reconciling', message: 'Đang kiểm tra kết quả của cùng thao tác.' });
    try {
      if (activeIntent.operationId) {
        const controller = new AbortController(); read.current = controller;
        const timer = setTimeout(() => controller.abort(), 15_000);
        let operation: Operation;
        try {
          operation = await apiClient<Operation>(`/api/v1/operations/${encodeURIComponent(activeIntent.operationId)}`, { cache: 'no-store', signal: controller.signal });
        } finally { clearTimeout(timer); read.current = null; }
        if (!alive.current) return;
        if (!validOperation(operation, activeIntent.operationId)) { unknown(activeIntent, 'Chưa xác định kết quả: biên nhận thao tác không hợp lệ.'); return; }
        if (operation.status === 'FAILED') {
          intent.current = null;
          show({ phase: 'terminal', message: 'Thao tác đã thất bại. Bấm Thử lại để bắt đầu thao tác mới.', requestId: activeIntent.requestId });
        } else if (operation.status === 'SUCCEEDED') {
          // T008 has no preview GET. A confirmed receipt is retrieved by same-key replay,
          // which the backend resolves before consent/admission and never dispatches again.
          if (visible.current) await send(activeIntent, true); else unknown(activeIntent);
        } else unknown(activeIntent, operation.status === 'PENDING' ? 'Chưa xác định: thao tác vẫn đang xử lý. Kiểm tra lại khi bạn muốn; không gửi lại AI.' : 'Chưa xác định kết quả ở nhà cung cấp. Không bắt đầu thao tác mới; chỉ kiểm tra lại biên nhận.');
      } else {
        // A lost response carries no operation ID. Explicit same-key replay retains
        // the original intent and still passes the established consent gate.
        await authorize(() => send(activeIntent, true));
      }
    } catch { unknown(activeIntent, 'Chưa xác định kết quả. Không đọc được API cục bộ; thao tác cũ vẫn được giữ để kiểm tra lại.'); }
    finally { busy.current = false; }
  };
  const waiting = busyPhases.includes(view.phase);
  return <section hidden={!active} aria-label="Tra cứu và xem trước" className="space-y-6 min-w-0 [overflow-wrap:anywhere]">
    <Card>
      <CardHeader><CardTitle><h2 className="m-0 text-xl">Tra cứu bằng AI</h2></CardTitle></CardHeader>
      <CardContent className="space-y-4 min-w-0">
        <form noValidate onSubmit={event => void submit(event)} className="space-y-3">
          <label htmlFor="lookup-term" className="block font-medium">Từ hoặc cụm từ cần tra cứu</label>
          <input id="lookup-term" ref={input} value={term} type="text" required autoComplete="off" spellCheck={false}
            aria-invalid={view.phase === 'validation'} aria-describedby="lookup-help lookup-status"
            className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            onChange={event => {
              setTerm(event.target.value); editVersion.current += 1; actionVersion.current += 1;
              if (!busy.current && !intent.current && !saveLock.current) show({ phase: 'idle', message: 'Nhập từ hoặc cụm từ để tra cứu.' });
            }} />
          <p id="lookup-help" className="text-sm text-muted-foreground">Tối đa 80 ký tự sau chuẩn hóa. Tra cứu chỉ tạo bản xem trước; chưa lưu vào kho học.</p>
          <Button type="submit" className="min-h-11" disabled={saveLocked || waiting || !!intent.current || consent.pending || !!consent.unresolved}>
            {view.phase === 'terminal' ? 'Thử lại' : 'Tra cứu'}
          </Button>
        </form>
        <p id="lookup-status" ref={status} tabIndex={-1} role={['validation', 'terminal', 'recoverable'].includes(view.phase) ? 'alert' : 'status'}
          aria-live={['validation', 'terminal', 'recoverable'].includes(view.phase) ? 'assertive' : 'polite'} aria-atomic="true"
          className="rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{view.message}</p>
        {(view.code || view.requestId) && <p className="text-sm text-muted-foreground break-words">{view.code} {view.requestId && `Mã yêu cầu: ${view.requestId}`}</p>}
        {intent.current?.operationId && <p className="text-sm break-words">Mã thao tác: {intent.current.operationId}</p>}
        {consent.error && <p role="alert">{consent.error}</p>}
        {view.phase === 'unknown' && <Button type="button" variant="outline" className="min-h-11" onClick={() => void reconcile()}>Kiểm tra kết quả</Button>}
        {view.phase === 'loading' && <Button type="button" variant="outline" className="min-h-11" onClick={() => post.current?.abort()}>Dừng chờ kết quả</Button>}
        {view.phase === 'loading' && <p className="text-sm text-muted-foreground">Dừng chờ không thu hồi dữ liệu đã gửi; kết quả có thể vẫn hoàn tất. Thao tác cũ sẽ được giữ để kiểm tra lại.</p>}
        {view.phase === 'loading' && <div aria-busy="true" aria-label="Đang tra cứu" className="space-y-3">
          <div className="h-6 rounded-md bg-muted motion-safe:animate-pulse" />
          <div className="h-16 rounded-md bg-muted motion-safe:animate-pulse" />
        </div>}
      </CardContent>
    </Card>
    {view.preview && <>
      <LookupResult preview={view.preview} savedNoteDate={saved?.lookupId === view.preview.lookupId ? saved.noteDate : undefined} />
      <Card role="region" aria-label="Phát âm cục bộ">
        <CardHeader><CardTitle><h2 className="m-0 text-xl">Phát âm cục bộ</h2></CardTitle></CardHeader>
        <CardContent className="space-y-4 min-w-0">
          {view.preview.forms.map(form => <div key={form.formId} className="space-y-2">
            <p className="text-sm text-muted-foreground">{form.partOfSpeech}</p>
            <AudioButton key={`${view.preview?.lookupId}-${form.formId}`} text={form.lemma} active={active} />
          </div>)}
        </CardContent>
      </Card>
    </>}
    <SavePreview preview={view.preview} active={active && !waiting && !intent.current} onLockChange={updateSaveLock} onConfirmed={confirmSave} />
  </section>;
}
