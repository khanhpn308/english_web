import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import { mapErrorToUIState, type UIErrorState } from '@/shared/api/errors';
import type { components, operations } from '@/shared/api/generated';
import { Flashcard } from './Flashcard';

type ReviewCard = components['schemas']['ReviewCardView'];
type QueueGet = operations['get_queue_api_v1_review_queue_get'];
type ReviewPost = operations['post_review_api_v1_cards__cardId__reviews_post'];
type Queue = QueueGet['responses'][200]['content']['application/json'];
type ReviewRequest = ReviewPost['requestBody']['content']['application/json'];
type ReviewEvent = ReviewPost['responses'][201]['content']['application/json'];
type WordDetail = components['schemas']['WordFormDetail'];
type Operation = components['schemas']['Operation'];
type Rating = ReviewRequest['rating'];
type Phase = 'idle' | 'loading' | 'ready' | 'empty' | 'error' | 'submitting' | 'unknown';
// Store only the immutable mutation fingerprint, never the word's learning content.
type Intent = { key: string; cardId: string; queueRevision: number; rating: Rating; noteDate: string; operationId?: string };
type View = { phase: Phase; message: string; recovery?: UIErrorState; code?: string };
const PENDING_KEY = 'vocabulary.review.pending.v1';
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const RATINGS = new Set<Rating>(['AGAIN', 'HARD', 'GOOD', 'EASY']);
const REJECTED = new Set(['REVISION_CONFLICT', 'NOT_FOUND', 'VALIDATION_ERROR', 'CROSS_RESOURCE_MISMATCH',
  'SESSION_REQUIRED', 'SESSION_INVALID', 'ORIGIN_FORBIDDEN', 'PAYLOAD_TOO_LARGE', 'INVALID_QUERY', 'CONFIGURATION_REQUIRED']);

function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
function identifier(value: unknown): value is string { return typeof value === 'string' && IDENTIFIER.test(value); }
function revision(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0; }
function timestamp(value: unknown): value is string { return typeof value === 'string' && Number.isFinite(Date.parse(value)); }
function verified(value: unknown) { return value === 'VERIFIED' || value === 'UNVERIFIED' || value === 'MISSING'; }
function urlNoteDate() {
  const value = typeof window === 'undefined' ? '' : new URLSearchParams(window.location.search).get('noteDate') ?? '';
  return DATE.test(value) ? value : '';
}
function validQueue(value: unknown): value is Queue {
  if (!record(value) || !Array.isArray(value.data) || !record(value.pagination) || !record(value.sort)) return false;
  const page = value.pagination;
  return value.data.every(card => record(card) && identifier(card.cardId) && identifier(card.wordFormId) &&
    typeof card.lemma === 'string' && Array.isArray(card.noteDates) &&
    card.noteDates.every(date => typeof date === 'string' && DATE.test(date)) &&
    (card.state === 'NEW' || card.state === 'LEARNED') && (card.dueAt === null || timestamp(card.dueAt)) && revision(card.queueRevision)) &&
    revision(page.pageSize) && page.pageSize >= 1 && page.pageSize <= 100 && value.data.length <= page.pageSize &&
    typeof page.hasMore === 'boolean' && (page.nextCursor === null || typeof page.nextCursor === 'string') &&
    (!page.hasMore || (typeof page.nextCursor === 'string' && page.nextCursor.length > 0)) &&
    new Set(value.data.map(card => card.cardId)).size === value.data.length &&
    (value.sort.by === 'dueAt' || value.sort.by === 'lemma') && (value.sort.direction === 'ASC' || value.sort.direction === 'DESC');
}
function validDetail(value: unknown, card: ReviewCard): value is WordDetail {
  if (!record(value)) return false;
  const meaning = (item: unknown) => record(item) && typeof item.text === 'string' &&
    typeof item.language === 'string' && verified(item.verificationStatus);
  return value.id === card.wordFormId && value.lemma === card.lemma && identifier(value.familyId) &&
    typeof value.partOfSpeech === 'string' && revision(value.revision) && timestamp(value.updatedAt) &&
    (value.ipaUs === null || typeof value.ipaUs === 'string') && (value.cambridgeUrl === null || typeof value.cambridgeUrl === 'string') &&
    Array.isArray(value.meaningsEn) && value.meaningsEn.every(meaning) && Array.isArray(value.meaningsVi) && value.meaningsVi.every(meaning) &&
    Array.isArray(value.examples) && value.examples.every(item => record(item) && typeof item.english === 'string' &&
      typeof item.vietnamese === 'string' && verified(item.verificationStatus)) && verified(value.verificationSummary) &&
    Array.isArray(value.sourceRefs) && value.sourceRefs.every(item => record(item) && identifier(item.sourceId) &&
      typeof item.noteDate === 'string' && DATE.test(item.noteDate) && ['VALID', 'INVALID', 'MISSING'].includes(String(item.status))) &&
    (value.card === null || (record(value.card) && value.card.id === card.cardId && typeof value.card.state === 'string' &&
      (value.card.dueAt === null || timestamp(value.card.dueAt))));
}
function validEvent(value: unknown, pending: Intent, resultRef?: string): value is ReviewEvent {
  return record(value) && value.cardId === pending.cardId && value.rating === pending.rating && value.source === 'FLASHCARD' &&
    identifier(value.id) && identifier(value.operationId) && timestamp(value.reviewedAt) && timestamp(value.nextDueAt) &&
    (pending.operationId === undefined || value.operationId === pending.operationId) &&
    (resultRef === undefined || value.id === resultRef) && value.attemptId == null && value.questionId == null;
}
function validOperation(value: unknown, id: string): value is Operation {
  return record(value) && value.operationId === id && value.kind === 'REVIEW' &&
    ['PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN'].includes(String(value.status)) && timestamp(value.createdAt) && timestamp(value.updatedAt) &&
    (value.resultRef == null || identifier(value.resultRef));
}
function restoredIntent(): { pending?: Intent; blocked: boolean } {
  if (typeof window === 'undefined') return { blocked: false };
  try {
    const raw = window.sessionStorage.getItem(PENDING_KEY);
    if (!raw) return { blocked: false };
    const value: unknown = JSON.parse(raw);
    if (record(value) && identifier(value.key) && identifier(value.cardId) && revision(value.queueRevision) &&
      typeof value.rating === 'string' && RATINGS.has(value.rating as Rating) && typeof value.noteDate === 'string' &&
      (value.noteDate === '' || DATE.test(value.noteDate)) && (value.operationId === undefined || identifier(value.operationId))) {
      return { pending: { key: value.key, cardId: value.cardId, queueRevision: value.queueRevision,
        rating: value.rating as Rating, noteDate: value.noteDate, ...(value.operationId ? { operationId: value.operationId } : {}) }, blocked: false };
    }
    return { blocked: true };
  } catch { return { blocked: true }; }
}
function operationId(error: unknown): string | undefined {
  if (error instanceof MutationUnknownError && identifier(error.operationId)) return error.operationId;
  if (error instanceof ApiError && error.details?.kind === 'RETRY' && identifier(error.details.operationId)) return error.details.operationId;
  return undefined;
}
function safeRecovery(error: unknown): UIErrorState {
  const recovery = mapErrorToUIState(error);
  return { ...recovery, requestId: identifier(recovery.requestId) ? recovery.requestId : undefined };
}
function errorMessage(error: unknown): string {
  if (error instanceof ApiError && typeof error.code === 'string') {
    if (error.code === 'REVISION_CONFLICT') return 'Thẻ đã thay đổi. Đọc lại hàng đợi trước khi đánh giá lại.';
    if (error.code === 'NOT_FOUND') return 'Thẻ không còn đủ điều kiện ôn từ nguồn hợp lệ. Đọc lại hàng đợi; lịch sử học được giữ.';
    if (error.code.startsWith('SESSION_')) return 'Phiên làm việc không còn hợp lệ. Mở lại ứng dụng từ launcher; thao tác đang chờ vẫn được giữ.';
    if (error.code === 'STORAGE_BUSY') return 'Kho dữ liệu đang bận. Kiểm tra kết quả của cùng thao tác trước khi đánh giá lại.';
    if (error.code === 'AI_CONSENT_REQUIRED' || error.code === 'AI_POLICY_CHANGED') return 'Quyền AI đã thay đổi. Kiểm tra quyền ở trang Trạng thái; chưa gửi lại đánh giá.';
    if (error.code === 'VALIDATION_ERROR' || error.code === 'CROSS_RESOURCE_MISMATCH') return 'Máy chủ từ chối đánh giá không hợp lệ. Thẻ được giữ; đọc lại dữ liệu trước khi tiếp tục.';
    if (error.code === 'ORIGIN_FORBIDDEN') return 'API từ chối nguồn truy cập. Mở ứng dụng từ launcher và kiểm tra Trạng thái.';
    if (error.code === 'IDEMPOTENCY_KEY_REUSED') return 'Danh tính thao tác không khớp. Giữ thao tác hiện tại; không tạo đánh giá mới.';
  }
  return 'Không đọc được dữ liệu ôn tập. Kiểm tra API cục bộ rồi thử lại; thẻ hiện tại được giữ.';
}

export function ReviewPage({ active = true }: { active?: boolean }) {
  const [restored] = useState(restoredIntent);
  const [storageBlocked, setStorageBlocked] = useState(restored.blocked);
  const [pending, setPending] = useState(restored.pending);
  const [noteDate, setNoteDate] = useState(() => {
    if (restored.pending) return restored.pending.noteDate;
    return urlNoteDate();
  });
  const [queue, setQueue] = useState<Queue>();
  const [detail, setDetail] = useState<WordDetail>();
  const [view, setView] = useState<View>({ phase: restored.pending ? 'unknown' : 'idle',
    message: restored.pending ? 'Chưa xác định kết quả đánh giá trước. Kiểm tra cùng thao tác trước khi tiếp tục.' : 'Chọn ngày ghi chú hoặc bắt đầu ôn tập.' });
  const [lastEvent, setLastEvent] = useState<ReviewEvent>();
  const intent = useRef(restored.pending);
  const busy = useRef(false);
  const alive = useRef(true);
  const visible = useRef(active);
  const sequence = useRef(0);
  const read = useRef<AbortController | null>(null);
  const status = useRef<HTMLParagraphElement>(null);
  const current = queue?.data[0];
  const show = useCallback((next: View) => { if (alive.current) setView(next); }, []);

  const remember = (next?: Intent) => {
    intent.current = next;
    if (alive.current) setPending(next);
    try {
      if (next) window.sessionStorage.setItem(PENDING_KEY, JSON.stringify(next));
      else window.sessionStorage.removeItem(PENDING_KEY);
      return true;
    } catch {
      if (alive.current) setStorageBlocked(true);
      return false;
    }
  };
  const unknown = (next: Intent, error?: unknown, message = 'Chưa xác định kết quả đánh giá. Kiểm tra cùng thao tác trước khi tiếp tục.') => {
    if (!alive.current) return;
    remember(next);
    show({ phase: 'unknown', message, ...(error ? { recovery: safeRecovery(error),
      code: error instanceof ApiError && /^[A-Z][A-Z0-9_]{0,79}$/.test(error.code) ? error.code : undefined } : {}) });
  };
  const reportError = useCallback((error: unknown, message = errorMessage(error)) => {
    show({ phase: 'error', message, recovery: safeRecovery(error),
      code: error instanceof ApiError && /^[A-Z][A-Z0-9_]{0,79}$/.test(error.code) ? error.code : undefined });
  }, [show]);

  const loadQueue = useCallback(async (selectedDate: string) => {
    if (!visible.current || intent.current || busy.current) return;
    const token = ++sequence.current;
    read.current?.abort();
    const controller = new AbortController(); read.current = controller;
    const timer = setTimeout(() => controller.abort(), 15_000);
    show({ phase: 'loading', message: 'Đang tải hàng đợi ôn tập.' });
    try {
      const query = { dueOnly: true, ...(selectedDate ? { noteDate: selectedDate } : {}) } satisfies NonNullable<QueueGet['parameters']['query']>;
      const params = Object.fromEntries(Object.entries(query).map(([key, value]) => [key, String(value)]));
      const value = await apiClient<Queue>('/api/v1/review-queue', { params, cache: 'no-store', signal: controller.signal });
      if (!alive.current || !visible.current || token !== sequence.current) return;
      if (controller.signal.aborted) throw new DOMException('Read aborted', 'AbortError');
      if (!validQueue(value)) throw new Error('Invalid queue response');
      setQueue(value); setDetail(undefined);
      if (!value.data.length) { show({ phase: 'empty', message: 'Không có thẻ đến hạn hoặc chưa học trong bộ lọc hiện tại.' }); return; }
      const card = value.data[0];
      const word = await apiClient<WordDetail>(`/api/v1/word-forms/${encodeURIComponent(card.wordFormId)}`, { cache: 'no-store', signal: controller.signal });
      if (!alive.current || !visible.current || token !== sequence.current) return;
      if (controller.signal.aborted) throw new DOMException('Read aborted', 'AbortError');
      if (!validDetail(word, card)) throw new Error('Invalid word detail');
      if (!word.sourceRefs.some(source => source.status === 'VALID') || !word.card || !['NEW', 'LEARNED'].includes(word.card.state)) {
        reportError(new Error('Inactive source'), 'Thẻ không còn nguồn hợp lệ để ôn. Đọc lại hàng đợi; lịch sử học được giữ.'); return;
      }
      setDetail(word);
      show({ phase: 'ready', message: `Đã tải thẻ ${card.lemma}. Lật thẻ để xem nghĩa rồi tự đánh giá.` });
    } catch (error) {
      if (!alive.current || !visible.current || token !== sequence.current) return;
      reportError(error);
    } finally {
      clearTimeout(timer);
      if (read.current === controller) read.current = null;
    }
  }, [reportError, show]);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; sequence.current += 1; read.current?.abort(); };
  }, []);
  useEffect(() => {
    visible.current = active;
    if (!active) { sequence.current += 1; read.current?.abort(); return; }
    if (intent.current) {
      if (!busy.current) show({ phase: 'unknown', message: 'Chưa xác định kết quả đánh giá trước. Kiểm tra cùng thao tác trước khi tiếp tục.' });
    } else if (!storageBlocked) {
      const selectedDate = urlNoteDate();
      if (selectedDate !== noteDate) setNoteDate(selectedDate);
      else void loadQueue(noteDate);
    }
  }, [active, loadQueue, noteDate, show, storageBlocked]);
  useEffect(() => {
    const restoreDate = () => {
      if (intent.current || busy.current) return;
      setNoteDate(urlNoteDate());
    };
    window.addEventListener('popstate', restoreDate);
    return () => window.removeEventListener('popstate', restoreDate);
  }, []);
  useEffect(() => {
    if (active && ['error', 'unknown', 'empty'].includes(view.phase)) status.current?.focus();
  }, [active, view]);

  const updateDate = (value: string) => {
    if (intent.current || busy.current || storageBlocked || (value && !DATE.test(value))) return;
    setNoteDate(value); setLastEvent(undefined);
    const url = new URL(window.location.href);
    if (value) url.searchParams.set('noteDate', value); else url.searchParams.delete('noteDate');
    window.history.pushState(null, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const runReview = async (next: Intent, replay = false, resultRef?: string) => {
    show({ phase: 'submitting', message: replay ? 'Đang đọc lại biên nhận của cùng đánh giá.' : 'Đang ghi nhận đánh giá.' });
    // The pending intent is already stored. A timeout is an unknown outcome, never a failed event.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15_000);
    try {
      const body = { rating: next.rating, source: 'FLASHCARD' } satisfies ReviewRequest;
      const headers = { 'If-Match': `"${next.queueRevision}"`, 'Idempotency-Key': next.key } satisfies ReviewPost['parameters']['header'];
      const value = await apiClient<ReviewEvent>(`/api/v1/cards/${encodeURIComponent(next.cardId)}/reviews`, {
        method: 'POST', body: JSON.stringify(body), headers, signal: controller.signal,
      });
      if (!validEvent(value, next, resultRef)) throw new Error('Invalid review receipt');
      // An unmounted instance leaves the stored intent for explicit replay. It must
      // never overwrite an intent being recovered by a newly mounted instance.
      if (!alive.current) return;
      remember();
      window.dispatchEvent(new CustomEvent('vocabulary:invalidate', { detail: { reason: 'review-recorded' } }));
      setLastEvent(value);
      show({ phase: 'idle', message: 'Đánh giá đã được máy chủ ghi nhận. Đọc lại hàng đợi để tiếp tục.' });
      busy.current = false;
      const selectedDate = urlNoteDate();
      // Navigation can change the URL while an old intent is unresolved. Its
      // fingerprint stays fixed; the confirmed queue uses the current route filter.
      if (selectedDate !== noteDate) setNoteDate(selectedDate);
      else await loadQueue(selectedDate);
    } catch (error) {
      if (!alive.current) return;
      const id = operationId(error);
      if (id && next.operationId && id !== next.operationId) { unknown(next, error); return; }
      // A rejection during replay cannot settle a previously ambiguous attempt.
      // IDEMPOTENCY_KEY_REUSED also retains its identity for investigation.
      if (!replay && error instanceof ApiError && REJECTED.has(error.code)) {
        remember(); reportError(error);
      } else unknown({ ...next, ...(id ? { operationId: id } : {}) }, error);
    } finally { clearTimeout(timer); }
  };
  const rate = async (rating: Rating) => {
    if (!visible.current || !alive.current || busy.current || intent.current || storageBlocked ||
      view.phase !== 'ready' || !current || !detail || !RATINGS.has(rating)) return;
    busy.current = true;
    const next: Intent = { key: crypto.randomUUID(), cardId: current.cardId, queueRevision: current.queueRevision, rating, noteDate };
    if (!remember(next)) {
      intent.current = undefined; setPending(undefined); busy.current = false;
      show({ phase: 'error', message: 'Không lưu được danh tính đánh giá. Chưa gửi yêu cầu; kiểm tra bộ nhớ trình duyệt trước khi tiếp tục.' }); return;
    }
    setLastEvent(undefined);
    try { await runReview(next); } finally { busy.current = false; }
  };
  const reconcile = async () => {
    const next = intent.current;
    if (!next || busy.current || !visible.current || !alive.current) return;
    busy.current = true;
    const token = ++sequence.current;
    read.current?.abort();
    show({ phase: 'submitting', message: 'Đang kiểm tra biên nhận đánh giá.' });
    try {
      let resultRef: string | undefined;
      if (next.operationId) {
        const controller = new AbortController(); read.current = controller;
        const timer = setTimeout(() => controller.abort(), 15_000);
        let operation: Operation;
        try {
          operation = await apiClient<Operation>(`/api/v1/operations/${encodeURIComponent(next.operationId)}`, { cache: 'no-store', signal: controller.signal });
        } finally { clearTimeout(timer); if (read.current === controller) read.current = null; }
        if (!alive.current) return;
        if (!visible.current || token !== sequence.current || controller.signal.aborted) { unknown(next); return; }
        if (!validOperation(operation, next.operationId)) { unknown(next); return; }
        if (operation.status === 'FAILED') {
          remember(); show({ phase: 'error', message: 'Thao tác đánh giá đã thất bại. Thẻ được giữ; đọc lại hàng đợi trước khi đánh giá lại.' }); return;
        }
        if (operation.status !== 'SUCCEEDED' || !operation.resultRef) {
          unknown(next, undefined, 'Chưa xác định kết quả. Biên nhận chưa hoàn tất; kiểm tra lại sau, không tạo đánh giá mới.'); return;
        }
        resultRef = operation.resultRef;
      }
      if (visible.current) await runReview(next, true, resultRef);
      else unknown(next);
    } catch (error) {
      if (token !== sequence.current || !visible.current) unknown(next);
      else unknown(next, error);
    }
    finally { busy.current = false; }
  };

  const waiting = view.phase === 'loading' || view.phase === 'submitting';
  const action = view.recovery?.actionType;
  const reread = () => {
    const selectedDate = urlNoteDate();
    if (selectedDate !== noteDate) setNoteDate(selectedDate);
    else void loadQueue(selectedDate);
  };
  return <section hidden={!active} aria-label="Hàng đợi ôn tập flashcard" className="space-y-6 min-w-0 [overflow-wrap:anywhere]">
    <Card>
      <CardHeader><CardTitle><h2 className="m-0 text-xl">Bộ lọc ôn tập</h2></CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-2 min-w-0">
            <label htmlFor="review-note-date" className="block font-medium">Ngày ghi chú</label>
            <input id="review-note-date" type="date" value={noteDate} disabled={!!pending || view.phase === 'submitting' || storageBlocked}
              onChange={event => updateDate(event.target.value)} aria-describedby="review-filter-help"
              className="min-h-11 max-w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring" />
          </div>
          <Button type="button" variant="outline" className="min-h-11" onClick={() => updateDate('')}
            disabled={!!pending || view.phase === 'submitting' || storageBlocked || !noteDate}>Tất cả ngày</Button>
        </div>
        <p id="review-filter-help" className="text-sm text-muted-foreground">Chỉ hiển thị thẻ đến hạn hoặc chưa học. Hàng đợi và lịch ôn do máy chủ cung cấp; nguồn không hợp lệ bị loại khỏi ôn tập.</p>
        <p id="review-status" ref={status} tabIndex={-1} role={view.phase === 'error' || view.phase === 'unknown' ? 'alert' : 'status'}
          aria-live={view.phase === 'error' || view.phase === 'unknown' ? 'assertive' : 'polite'} aria-atomic="true"
          className="rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{view.message}</p>
        {view.phase === 'unknown' && action === 'REBOOTSTRAP' && <p>Mở lại ứng dụng từ launcher để khôi phục phiên, rồi kiểm tra cùng đánh giá. Không tạo đánh giá mới.</p>}
        {view.phase === 'unknown' && action === 'UPDATE_CONSENT' && <p>Kiểm tra quyền AI ở trang Trạng thái. Đánh giá đang chờ vẫn được giữ và chưa gửi lại.</p>}
        {storageBlocked && <p role="alert">Không đọc hoặc lưu được danh tính thao tác trong bộ nhớ phiên. Đã khóa đánh giá mới để tránh ghi trùng; giữ tab này và kiểm tra Trạng thái.</p>}
        {pending && <p>Đánh giá đang chờ xác nhận: {pending.rating}. Thẻ: {pending.cardId}.</p>}
        {(view.code || view.recovery?.requestId || pending?.operationId) && <details className="text-sm break-words">
          <summary className="cursor-pointer">Chi tiết hỗ trợ</summary>
          {view.code && <p>{view.code}</p>}
          {view.recovery?.requestId && <p>Mã yêu cầu: {view.recovery.requestId}</p>}
          {pending?.operationId && <p>Mã thao tác: {pending.operationId}</p>}
        </details>}
        {lastEvent && <p role="status">Đã ghi nhận đánh giá {lastEvent.rating}. Lịch tiếp theo: <time dateTime={lastEvent.nextDueAt}>{lastEvent.nextDueAt}</time></p>}
        {!waiting && pending && <Button type="button" variant="outline" className="min-h-11" onClick={() => void reconcile()}>Kiểm tra kết quả</Button>}
        {!waiting && !pending && !storageBlocked && view.phase === 'error' && action !== 'REBOOTSTRAP' && action !== 'UPDATE_CONSENT' &&
          <Button type="button" variant="outline" className="min-h-11" onClick={reread}>
            {action === 'RELOAD' || view.code === 'NOT_FOUND' ? 'Đọc lại hàng đợi' : 'Thử lại'}
          </Button>}
        {(view.phase === 'error' || view.phase === 'unknown' || storageBlocked) && <a href="/status" className="inline-block underline text-primary p-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Kiểm tra Trạng thái</a>}
        {queue && <p className="text-sm text-muted-foreground">Trang máy chủ trả về: {queue.data.length} thẻ{queue.pagination.hasMore ? ', còn trang tiếp theo' : ''}. Sau mỗi đánh giá đã xác nhận, hàng đợi được đọc lại từ trang đầu.</p>}
      </CardContent>
    </Card>
    {view.phase === 'loading' && <Card aria-busy="true" aria-label="Đang tải thẻ"><CardContent className="pt-6 space-y-3">
      <div className="h-6 rounded-md bg-muted motion-safe:animate-pulse" /><div className="h-16 rounded-md bg-muted motion-safe:animate-pulse" />
    </CardContent></Card>}
    {view.phase === 'empty' && <Card role="status"><CardContent className="pt-6"><p>Không có thẻ đến hạn hoặc chưa học.</p></CardContent></Card>}
    {current && <Flashcard key={`${current.cardId}:${current.queueRevision}`} card={current} detail={detail}
      disabled={view.phase !== 'ready' || !!pending || storageBlocked || !active || !detail} onRate={rating => void rate(rating)} />}
  </section>;
}
