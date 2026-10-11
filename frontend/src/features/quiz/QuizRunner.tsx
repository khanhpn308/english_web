import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ApiError, MutationUnknownError, apiClient, getETag } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';
import { QuestionRenderer } from './QuestionRenderer';

type QuizAttempt = components['schemas']['QuizAttempt'];
type Answer = components['schemas']['Answer'];
type AnswerDraftRequest = components['schemas']['AnswerDraftRequest'];
type SyncStatus = 'idle' | 'pending' | 'saving' | 'saved' | 'error' | 'conflict' | 'unknown' | 'reconciling';

type Mutation = {
  answer: string;
  selfScore: number | null;
  revision: number;
  etag: string;
  key: string;
};

interface QuestionState {
  serverRevision: number;
  serverEtag: string;
  serverAnswer: string;
  serverSelfScore: number | null;
  localAnswer: string;
  localSelfScore: number | null;
  status: SyncStatus;
  active: Mutation | null;
  uncertain: Mutation | null;
  conflictLoaded: boolean;
}

const validEtag = (value: string): boolean => /^"qa-v1-[0-9a-f]{64}"$/.test(value);
const sameDraft = (a: string, score: number | null, b: string, otherScore: number | null) =>
  a === b && score === otherScore;

export const QuizRunner: React.FC<{ attemptId: string }> = ({ attemptId }) => {
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [states, setStates] = useState<Record<string, QuestionState>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // The ref is the synchronous authority for in-flight requests and blur handlers.
  // React state is a read-only rendering snapshot, never an implicit network lock.
  const live = useRef<Record<string, QuestionState>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const epoch = useRef(0);

  const publish = useCallback(() => {
    setStates(Object.fromEntries(Object.entries(live.current).map(([id, state]) => [id, { ...state }])));
  }, []);

  const cancelTimers = useCallback(() => {
    Object.values(timers.current).forEach(clearTimeout);
    timers.current = {};
  }, []);

  const readAttempt = useCallback(async (): Promise<QuizAttempt> => {
    const data = await apiClient<QuizAttempt>('/api/v1/quiz-attempts/' + encodeURIComponent(attemptId), {
      cache: 'no-store',
    });
    if (!data || data.id !== attemptId || !Array.isArray(data.questions) ||
        !Array.isArray(data.answerPreconditions) || !Array.isArray(data.answers)) {
      throw new Error('Invalid quiz restore response');
    }
    for (const question of data.questions) {
      const precondition = data.answerPreconditions.find(p => p.questionId === question.id);
      if (!precondition || !validEtag(precondition.etag)) {
        throw new Error('Missing quiz draft precondition');
      }
    }
    return data;
  }, [attemptId]);

  useEffect(() => {
    const generation = ++epoch.current;
    cancelTimers();
    live.current = {};
    void readAttempt().then(data => {
      if (generation !== epoch.current) return;
      const restored: Record<string, QuestionState> = {};
      for (const question of data.questions) {
        const precondition = data.answerPreconditions.find(p => p.questionId === question.id)!;
        const answer = data.answers.find(a => a.questionId === question.id);
        restored[question.id] = {
          serverRevision: precondition.draftRevision,
          serverEtag: precondition.etag,
          serverAnswer: answer?.answer ?? '',
          serverSelfScore: answer?.selfScore ?? null,
          localAnswer: answer?.answer ?? '',
          localSelfScore: answer?.selfScore ?? null,
          status: 'idle',
          active: null,
          uncertain: null,
          conflictLoaded: false,
        };
      }
      live.current = restored;
      setAttempt(data);
      publish();
    }).catch(() => {
      if (generation === epoch.current) {
        setErrorMsg('Không thể tải bài kiểm tra. Vui lòng kiểm tra API cục bộ hoặc phiên làm việc.');
      }
    });
    return () => {
      ++epoch.current;
      cancelTimers();
    };
  }, [cancelTimers, publish, readAttempt]);

  const save: (questionId: string, replay?: Mutation) => Promise<void> = useCallback(async (questionId, replay) => {
    const state = live.current[questionId];
    if (!state || state.active || attempt?.status === 'SUBMITTED') return;
    if (!replay && ['unknown', 'conflict', 'reconciling'].includes(state.status)) return;
    if (!replay && sameDraft(state.localAnswer, state.localSelfScore, state.serverAnswer, state.serverSelfScore)) {
      state.status = 'saved';
      publish();
      return;
    }
    if (!validEtag(state.serverEtag)) {
      state.status = 'error';
      publish();
      return;
    }

    const mutation = replay ?? {
      answer: state.localAnswer,
      selfScore: state.localSelfScore,
      revision: state.serverRevision,
      etag: state.serverEtag,
      key: crypto.randomUUID(),
    };
    state.active = mutation; // Acquire lock synchronously before the first await.
    state.status = 'saving';
    state.uncertain = null;
    publish();
    const generation = epoch.current;

    try {
      // An explicit null is required to clear an earlier writing self-score.
      const body: AnswerDraftRequest = {
        answer: mutation.answer,
        selfScore: mutation.selfScore,
        draftRevision: mutation.revision,
      };
      const response = await apiClient<Answer>(
        '/api/v1/quiz-attempts/' + encodeURIComponent(attemptId) + '/answers/' + encodeURIComponent(questionId),
        {
          method: 'PUT',
          body: JSON.stringify(body),
          headers: { 'If-Match': mutation.etag, 'Idempotency-Key': mutation.key },
        },
      );
      if (generation !== epoch.current || live.current[questionId] !== state) return;
      const etag = getETag(response);
      if (!response || response.attemptId !== attemptId || response.questionId !== questionId ||
          response.draftRevision !== mutation.revision + 1 || !etag || !validEtag(etag) ||
          !sameDraft(response.answer, response.selfScore, mutation.answer, mutation.selfScore)) {
        // A malformed/missing receipt cannot establish a durable write.
        state.active = null;
        state.uncertain = mutation;
        state.status = 'unknown';
        publish();
        return;
      }
      state.serverRevision = response.draftRevision;
      state.serverEtag = etag;
      state.serverAnswer = response.answer;
      state.serverSelfScore = response.selfScore;
      state.active = null;
      const dirty = !sameDraft(state.localAnswer, state.localSelfScore, state.serverAnswer, state.serverSelfScore);
      state.status = dirty ? 'pending' : 'saved';
      publish();
      // A newer edit cannot be overwritten by this older receipt.
      if (dirty && !timers.current[questionId]) void save(questionId);
    } catch (error) {
      if (generation !== epoch.current || live.current[questionId] !== state) return;
      state.active = null;
      if (error instanceof MutationUnknownError ||
          (error instanceof ApiError && (error.status >= 500 || error.code === 'IDEMPOTENCY_IN_FLIGHT'))) {
        state.uncertain = mutation;
        state.status = 'unknown';
      } else if (error instanceof ApiError && error.code === 'REVISION_CONFLICT') {
        state.status = 'conflict';
        state.conflictLoaded = false;
      } else {
        state.status = 'error';
      }
      publish();
    }
  }, [attempt?.status, attemptId, publish]);

  const reconcile = useCallback(async (questionId: string): Promise<void> => {
    const state = live.current[questionId];
    if (!state || state.active || state.status === 'reconciling') return;
    const uncertain = state.uncertain;
    const wasConflict = state.status === 'conflict';
    state.status = 'reconciling';
    publish();
    const generation = epoch.current;
    try {
      const snapshot = await readAttempt();
      if (generation !== epoch.current || live.current[questionId] !== state) return;
      const pre = snapshot.answerPreconditions.find(p => p.questionId === questionId);
      if (!pre || !validEtag(pre.etag)) throw new Error('Invalid precondition');
      const saved = snapshot.answers.find(a => a.questionId === questionId);
      const serverAnswer = saved?.answer ?? '';
      const serverScore = saved?.selfScore ?? null;
      state.serverRevision = pre.draftRevision;
      state.serverEtag = pre.etag;
      state.serverAnswer = serverAnswer;
      state.serverSelfScore = serverScore;
      setAttempt(snapshot);

      if (snapshot.status === 'SUBMITTED') {
        state.status = 'conflict';
        state.uncertain = null;
        state.conflictLoaded = false;
      } else if (uncertain && pre.draftRevision === uncertain.revision + 1 &&
                 sameDraft(serverAnswer, serverScore, uncertain.answer, uncertain.selfScore)) {
        state.uncertain = null;
        state.status = sameDraft(state.localAnswer, state.localSelfScore, serverAnswer, serverScore)
          ? 'saved' : 'pending';
      } else if (uncertain && pre.draftRevision === uncertain.revision && pre.etag === uncertain.etag) {
        // GET first, then replay the *exact same* identity/payload/precondition.
        state.uncertain = null;
        state.status = 'pending';
        publish();
        await save(questionId, uncertain);
        return;
      } else if (uncertain || wasConflict) {
        state.uncertain = null;
        state.status = 'conflict';
        state.conflictLoaded = true;
      } else {
        state.status = sameDraft(state.localAnswer, state.localSelfScore, serverAnswer, serverScore)
          ? 'saved' : 'conflict';
        state.conflictLoaded = state.status === 'conflict';
      }
      publish();
      if (state.status === 'pending') void save(questionId);
    } catch {
      if (generation !== epoch.current || live.current[questionId] !== state) return;
      state.status = uncertain ? 'unknown' : 'conflict';
      state.uncertain = uncertain;
      state.conflictLoaded = false;
      setErrorMsg('Không đối soát được bản nháp. Dữ liệu đang nhập vẫn ở tab này; hãy thử lại khi API sẵn sàng.');
      publish();
    }
  }, [publish, readAttempt, save]);

  const changeAnswer = (id: string, answer: string, score: number | null) => {
    const state = live.current[id];
    if (!state || attempt?.status === 'SUBMITTED') return;
    state.localAnswer = answer;
    state.localSelfScore = score;
    if (!['unknown', 'conflict', 'reconciling'].includes(state.status)) {
      state.status = state.active ? 'saving' : 'pending';
    }
    publish();
    clearTimeout(timers.current[id]);
    if (!['unknown', 'conflict', 'reconciling'].includes(state.status)) {
      timers.current[id] = setTimeout(() => {
        delete timers.current[id];
        void save(id);
      }, 500);
    }
  };

  const flush = (id: string) => {
    clearTimeout(timers.current[id]);
    delete timers.current[id];
    void save(id);
  };

  const resolveConflict = (id: string, keepLocal: boolean) => {
    const state = live.current[id];
    if (!state?.conflictLoaded || state.active || attempt?.status === 'SUBMITTED') return;
    if (!keepLocal) {
      state.localAnswer = state.serverAnswer;
      state.localSelfScore = state.serverSelfScore;
      state.status = 'saved';
      state.conflictLoaded = false;
      publish();
      return;
    }
    // Explicit user choice after reading both versions. Next PUT still uses CAS.
    state.status = 'pending';
    state.conflictLoaded = false;
    publish();
    void save(id);
  };

  const retryLoad = () => {
    // A failed initial GET has no local draft. Remount without a full-page reload.
    setErrorMsg(null);
    const generation = ++epoch.current;
    cancelTimers();
    void readAttempt().then(data => {
      if (generation !== epoch.current) return;
      const restored: Record<string, QuestionState> = {};
      for (const question of data.questions) {
        const pre = data.answerPreconditions.find(p => p.questionId === question.id)!;
        const previous = live.current[question.id];
        const answer = data.answers.find(a => a.questionId === question.id);
        restored[question.id] = {
          serverRevision: pre.draftRevision, serverEtag: pre.etag,
          serverAnswer: answer?.answer ?? '', serverSelfScore: answer?.selfScore ?? null,
          localAnswer: previous?.localAnswer ?? answer?.answer ?? '',
          localSelfScore: previous?.localSelfScore ?? answer?.selfScore ?? null,
          status: previous ? 'conflict' : 'idle',
          active: null, uncertain: null, conflictLoaded: !!previous,
        };
      }
      live.current = restored;
      setAttempt(data);
      publish();
    }).catch(() => {
      if (generation === epoch.current) {
        setErrorMsg('Không thể tải bài kiểm tra. Vui lòng kiểm tra API cục bộ hoặc phiên làm việc.');
      }
    });
  };

  const displayedAttempt = attempt?.id === attemptId ? attempt : null;
  if (!displayedAttempt) {
    return errorMsg ? (
      <Card role="alert">
        <CardHeader><CardTitle>Lỗi tải bài kiểm tra</CardTitle></CardHeader>
        <CardContent>
          <p>{errorMsg}</p>
          <Button onClick={retryLoad}>Thử lại</Button>
        </CardContent>
      </Card>
    ) : <Card><CardContent role="status">Đang tải bài kiểm tra...</CardContent></Card>;
  }

  const submitted = displayedAttempt.status === 'SUBMITTED';
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Card><CardHeader><CardTitle>Làm bài kiểm tra</CardTitle></CardHeader></Card>
      {errorMsg && <p role="alert" className="text-destructive">{errorMsg}</p>}
      {displayedAttempt.questions.map(question => {
        const state = states[question.id];
        if (!state) return null;
        return (
          <div key={question.id} className="space-y-2">
            <QuestionRenderer
              question={question}
              answerDraft={state.localAnswer}
              selfScoreDraft={state.localSelfScore}
              onChange={(answer, score) => changeAnswer(question.id, answer, score)}
              onBlur={() => flush(question.id)}
              disabled={submitted}
            />
            {!submitted && (
              <div className="space-y-2 text-sm" role="status" aria-live="polite">
                {state.status === 'pending' && <span>Chưa lưu</span>}
                {state.status === 'saving' && <span>Đang lưu...</span>}
                {state.status === 'saved' && <span>Đã lưu</span>}
                {state.status === 'error' && (
                  <div className="flex items-center gap-3">
                    <span className="text-destructive">Lỗi lưu, bản nhập chưa được xác nhận.</span>
                    <Button variant="outline" size="sm" onClick={() => flush(question.id)}>Thử lại</Button>
                  </div>
                )}
                {(state.status === 'unknown' || state.status === 'reconciling') && (
                  <div className="flex items-center gap-3">
                    <span className="text-destructive">
                      {state.status === 'reconciling' ? 'Đang đối soát...' : 'Chưa rõ kết quả lưu'}
                    </span>
                    {state.status === 'unknown' && (
                      <Button variant="outline" size="sm" onClick={() => void reconcile(question.id)}>
                        Kiểm tra bản đã lưu
                      </Button>
                    )}
                  </div>
                )}
                {state.status === 'conflict' && (
                  <div className="space-y-2">
                    <p className="text-destructive">Xung đột phiên bản. Chưa ghi đè dữ liệu trên máy chủ.</p>
                    {!state.conflictLoaded ? (
                      <Button variant="outline" size="sm" onClick={() => void reconcile(question.id)}>
                        Đọc phiên bản máy chủ
                      </Button>
                    ) : (
                      <div className="space-y-2">
                        <p className="whitespace-pre-wrap break-words">Máy chủ: {state.serverAnswer || '(trống)'} {state.serverSelfScore !== null ? '(điểm ' + state.serverSelfScore + ')' : ''}</p>
                        <p className="whitespace-pre-wrap break-words">Bản đang nhập: {state.localAnswer || '(trống)'} {state.localSelfScore !== null ? '(điểm ' + state.localSelfScore + ')' : ''}</p>
                        <div className="flex flex-wrap gap-2">
                          <Button variant="outline" size="sm" onClick={() => resolveConflict(question.id, false)}>Dùng bản máy chủ</Button>
                          <Button size="sm" onClick={() => resolveConflict(question.id, true)}>Lưu bản đang nhập</Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      <Card>
        <CardContent className="space-y-3 p-6">
          <p className="text-sm text-muted-foreground">
            Bản nháp được lưu qua API cục bộ. Nếu có thông báo chưa lưu, không đóng tab.
            Nộp bài sẽ được tích hợp trong T051 sau khi T048 hoàn thành.
          </p>
          <Button disabled>Nộp bài (Chưa khả dụng)</Button>
        </CardContent>
      </Card>
    </div>
  );
};
