import React, { useState, useRef, useCallback, useEffect, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { useAiConsent } from '@/features/consent/AiConsentGate';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';

type CreateQuizRequest = components['schemas']['CreateQuizRequest'];
type QuizAttempt = components['schemas']['QuizAttempt'];
type Operation = components['schemas']['Operation'];
type Intent = { key: string; requestId: string; counts: { mcq: number; cloze: number; writing: number }; noteDate: string; edit: number; operationId?: string };
type Phase = 'idle' | 'validation' | 'authorizing' | 'loading' | 'recoverable' | 'terminal' | 'unknown' | 'reconciling';

interface View {
  phase: Phase;
  message: string;
  requestId?: string;
  code?: string;
}

export function QuizBuilder({ path, onNavigate }: { path?: string; onNavigate?: (path: string) => void }) {
  const consent = useAiConsent();
  const [mcqCount, setMcqCount] = useState('2');
  const [clozeCount, setClozeCount] = useState('2');
  const [writingCount, setWritingCount] = useState('1');
  const [noteDate, setNoteDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [view, setView] = useState<View>({ phase: 'idle', message: 'Chọn số lượng câu hỏi và ngày học để tạo bài kiểm tra.' });

  const statusRef = useRef<HTMLParagraphElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);

  const alive = useRef(true);
  const busy = useRef(false);
  const editVersion = useRef(0);
  const actionVersion = useRef(0);
  const intent = useRef<Intent | null>(null);
  const read = useRef<AbortController | null>(null);
  const post = useRef<AbortController | null>(null);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; actionVersion.current += 1; read.current?.abort(); };
  }, []);

  useEffect(() => {
    if (view.phase === 'idle' || view.phase === 'loading' || view.phase === 'authorizing' || view.phase === 'reconciling') return;
    if (document.activeElement?.closest('[role="dialog"]')) return;
    if (view.phase === 'validation') firstInputRef.current?.focus();
    else statusRef.current?.focus();
  }, [view]);

  const show = (next: View) => { if (alive.current) setView(next); };

  const unknown = (activeIntent: Intent, message = 'Chưa xác định kết quả thao tác. Kiểm tra kết quả trước khi tạo mới.') => {
    intent.current = activeIntent;
    show({ phase: 'unknown', message, requestId: activeIntent.requestId });
  };

  const complete = (attemptId: string) => {
    intent.current = null;
    show({ phase: 'idle', message: 'Tạo bài kiểm tra thành công. Đang chuyển hướng...' });
    if (onNavigate) {
      onNavigate(`/quiz/${attemptId}`);
    }
  };

  const send = async (activeIntent: Intent, replay = false) => {
    intent.current = activeIntent;
    show({ phase: 'loading', message: 'Đang tạo bài kiểm tra...' });
    const controller = new AbortController();
    post.current = controller;
    const timer = setTimeout(() => controller.abort(), 60_000); // 60s generation deadline
    try {
      const payload: CreateQuizRequest = {
        counts: activeIntent.counts,
        noteDate: activeIntent.noteDate,
      };

      const data = await apiClient<QuizAttempt>('/api/v1/quiz-attempts', {
        method: 'POST',
        body: JSON.stringify(payload),
        headers: { 'Idempotency-Key': activeIntent.key, 'X-Request-ID': activeIntent.requestId },
        signal: controller.signal,
      });

      if (!alive.current) return;
      if (!data || !data.id) {
        unknown(activeIntent, 'Chưa xác định kết quả: phản hồi không hợp lệ.');
        return;
      }

      complete(data.id);
    } catch (failure) {
      if (!alive.current) return;
      if (failure instanceof ApiError) {
        const code = typeof failure.code === 'string' && /^[A-Z][A-Z0-9_]{0,79}$/.test(failure.code) ? failure.code : 'INTERNAL_ERROR';
        const operationId = failure.details?.kind === 'RETRY' ? failure.details.operationId : undefined;
        if (activeIntent.operationId && operationId && operationId !== activeIntent.operationId) {
          unknown(activeIntent, 'Chưa xác định kết quả: mã thao tác trong phản hồi không khớp.'); return;
        }
        if (operationId) activeIntent.operationId = operationId;
        const requestId = failure.requestId || activeIntent.requestId;

        if (replay && ['BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE'].includes(code)) {
          intent.current = null;
          show({ phase: 'terminal', message: 'Thao tác đã thất bại. Bấm Thử lại để bắt đầu thao tác mới.', code, requestId });
        } else if (replay || activeIntent.operationId || code === 'IDEMPOTENCY_IN_FLIGHT') {
          show({ phase: 'unknown', message: 'Chưa xác định kết quả thao tác. Kiểm tra kết quả trước khi tạo mới.', code, requestId });
        } else if (['AI_CONSENT_REQUIRED', 'VALIDATION_ERROR', 'FIELD_ERRORS', 'CONFIGURATION_REQUIRED', 'BRIDGE_AUTH_ERROR', 'BRIDGE_INVALID_RESPONSE', 'NETWORK_REQUIRED', 'SESSION_REQUIRED', 'SESSION_INVALID', 'ORIGIN_FORBIDDEN'].includes(code) || failure.status < 500) {
          intent.current = null;
          let msg = 'Không tạo được bài kiểm tra. Kiểm tra trạng thái API và bridge trước khi chủ động thử lại.';
          if (code === 'AI_CONSENT_REQUIRED') msg = 'Quyền AI đã thay đổi. Đọc lại quyền; sau đó bấm Tạo bài kiểm tra khi bạn muốn gửi.';
          else if (code.startsWith('SESSION_')) msg = 'Phiên làm việc không còn hợp lệ. Mở lại ứng dụng từ launcher.';
          else if (code === 'VALIDATION_ERROR' || code === 'FIELD_ERRORS') msg = 'Dữ liệu không hợp lệ. Vui lòng kiểm tra lại số lượng hoặc ngày học. Có thể nguồn từ vựng chưa đủ.';

          show({ phase: code === 'AI_CONSENT_REQUIRED' ? 'recoverable' : 'terminal', code, requestId, message: msg });
          if (code === 'AI_CONSENT_REQUIRED') void consent.refresh();
        } else {
          unknown(activeIntent);
        }
      } else {
        if (failure instanceof MutationUnknownError && failure.operationId) activeIntent.operationId = failure.operationId;
        unknown(activeIntent);
      }
    } finally {
      clearTimeout(timer);
      post.current = null;
    }
  };

  const authorize = async (dispatch: () => Promise<void>) => {
    const version = actionVersion.current;
    let authorized = false;
    await consent.requestPermission(() => { authorized = version === actionVersion.current && alive.current; });
    if (authorized) await dispatch();
    else if (alive.current) {
      show({ phase: intent.current ? 'unknown' : version !== actionVersion.current ? 'idle' : 'recoverable',
        message: intent.current ? 'Chưa xác định kết quả thao tác cũ. Chưa gửi lại; sau khi chọn quyền AI, hãy bấm Kiểm tra kết quả.' :
          'Chưa gửi yêu cầu tạo. Sau khi chọn quyền AI, hãy bấm lại thao tác khi bạn muốn gửi.' });
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy.current || intent.current) return;

    const mcq = parseInt(mcqCount, 10);
    const cloze = parseInt(clozeCount, 10);
    const writing = parseInt(writingCount, 10);

    if (isNaN(mcq) || isNaN(cloze) || isNaN(writing) || mcq < 0 || cloze < 0 || writing < 0 || mcq > 20 || cloze > 20 || writing > 20) {
      show({ phase: 'validation', message: 'Số lượng câu hỏi mỗi loại phải là số nguyên từ 0 đến 20.' });
      return;
    }

    const total = mcq + cloze + writing;
    if (total < 5 || total > 30) {
      show({ phase: 'validation', message: 'Tổng số câu hỏi phải từ 5 đến 30 câu.' });
      return;
    }

    if (!/^\d{4}-\d{2}-\d{2}$/.test(noteDate) || isNaN(Date.parse(noteDate))) {
      show({ phase: 'validation', message: 'Ngày học không hợp lệ. Vui lòng nhập theo định dạng YYYY-MM-DD.' });
      return;
    }

    busy.current = true;
    const edit = editVersion.current;
    show({ phase: 'authorizing', message: 'Đang kiểm tra quyền AI...' });

    try {
      await authorize(async () => {
        await send({
          counts: { mcq, cloze, writing },
          noteDate,
          edit,
          key: crypto.randomUUID(),
          requestId: `req_${crypto.randomUUID()}`
        });
      });
    } catch {
      show({ phase: 'recoverable', message: 'Không đọc được quyền AI. Kiểm tra API cục bộ rồi bấm lại.' });
    } finally {
      busy.current = false;
    }
  };

  const reconcile = async () => {
    const activeIntent = intent.current;
    if (!activeIntent || busy.current) return;
    busy.current = true;
    show({ phase: 'reconciling', message: 'Đang kiểm tra kết quả của cùng thao tác.' });
    try {
      if (activeIntent.operationId) {
        const controller = new AbortController();
        read.current = controller;
        const timer = setTimeout(() => controller.abort(), 15_000);
        let operation: Operation;
        try {
          operation = await apiClient<Operation>(`/api/v1/operations/${encodeURIComponent(activeIntent.operationId)}`, { cache: 'no-store', signal: controller.signal });
        } finally {
          clearTimeout(timer);
          read.current = null;
        }

        if (!alive.current) return;
        if (!operation || operation.operationId !== activeIntent.operationId) {
          unknown(activeIntent, 'Chưa xác định kết quả: biên nhận thao tác không hợp lệ.');
          return;
        }

        if (operation.status === 'FAILED') {
          intent.current = null;
          show({ phase: 'terminal', message: 'Thao tác đã thất bại. Bấm Thử lại để bắt đầu thao tác mới.', requestId: activeIntent.requestId });
        } else if (operation.status === 'SUCCEEDED') {
          await send(activeIntent, true);
        } else {
          unknown(activeIntent, operation.status === 'PENDING' ? 'Chưa xác định: thao tác vẫn đang xử lý. Kiểm tra lại sau.' : 'Chưa xác định kết quả. Không bắt đầu thao tác mới; chỉ kiểm tra lại biên nhận.');
        }
      } else {
        await authorize(() => send(activeIntent, true));
      }
    } catch {
      unknown(activeIntent, 'Chưa xác định kết quả. Không đọc được API cục bộ; thao tác cũ vẫn được giữ để kiểm tra lại.');
    } finally {
      busy.current = false;
    }
  };

  const handleInputChange = (setter: React.Dispatch<React.SetStateAction<string>>) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setter(e.target.value);
    editVersion.current += 1;
    actionVersion.current += 1;
    if (!busy.current && !intent.current) show({ phase: 'idle', message: 'Chọn số lượng câu hỏi và ngày học để tạo bài kiểm tra.' });
  };

  const waiting = ['authorizing', 'loading', 'reconciling'].includes(view.phase);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Tạo Bài Kiểm Tra Bằng AI</CardTitle>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={event => void submit(event)} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="noteDate" className="block font-medium">Ngày học từ vựng</label>
              <input id="noteDate" type="date" value={noteDate} onChange={handleInputChange(setNoteDate)} required
                className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2" />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label htmlFor="mcqCount" className="block font-medium">Trắc nghiệm</label>
                <input id="mcqCount" type="number" min="0" max="20" step="1" ref={firstInputRef} value={mcqCount} onChange={handleInputChange(setMcqCount)} required
                  className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2" />
              </div>

              <div className="space-y-2">
                <label htmlFor="clozeCount" className="block font-medium">Điền từ</label>
                <input id="clozeCount" type="number" min="0" max="20" step="1" value={clozeCount} onChange={handleInputChange(setClozeCount)} required
                  className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2" />
              </div>

              <div className="space-y-2">
                <label htmlFor="writingCount" className="block font-medium">Tự luận</label>
                <input id="writingCount" type="number" min="0" max="20" step="1" value={writingCount} onChange={handleInputChange(setWritingCount)} required
                  className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2" />
              </div>
            </div>

            <div className="pt-2 flex flex-col gap-3">
              <Button type="submit" className="min-h-11 w-full sm:w-auto self-start" disabled={waiting || !!intent.current || consent.pending || !!consent.unresolved}>
                {view.phase === 'terminal' ? 'Thử lại' : 'Tạo bài kiểm tra'}
              </Button>
            </div>
          </form>

          <div className="mt-6 space-y-3">
            <p id="quiz-status" ref={statusRef} tabIndex={-1} role={['validation', 'terminal', 'recoverable'].includes(view.phase) ? 'alert' : 'status'}
              aria-live={['validation', 'terminal', 'recoverable'].includes(view.phase) ? 'assertive' : 'polite'} aria-atomic="true"
              className="rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2">{view.message}</p>

            {(view.code || view.requestId) && <p className="text-sm text-muted-foreground break-words">{view.code} {view.requestId && `Mã yêu cầu: ${view.requestId}`}</p>}
            {intent.current?.operationId && <p className="text-sm break-words">Mã thao tác: {intent.current.operationId}</p>}
            {consent.error && <p role="alert">{consent.error}</p>}

            {view.phase === 'unknown' && <Button type="button" variant="outline" className="min-h-11" onClick={() => void reconcile()}>Kiểm tra kết quả</Button>}
            {view.phase === 'loading' && <Button type="button" variant="outline" className="min-h-11" onClick={() => post.current?.abort()}>Dừng chờ kết quả</Button>}
            {view.phase === 'loading' && <p className="text-sm text-muted-foreground">Dừng chờ không thu hồi dữ liệu đã gửi; thao tác cũ sẽ được giữ để kiểm tra lại.</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
