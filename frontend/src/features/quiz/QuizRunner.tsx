import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';
import { QuestionRenderer } from './QuestionRenderer';

type QuizAttempt = components['schemas']['QuizAttempt'];
type Answer = components['schemas']['Answer'];
type AnswerDraftRequest = components['schemas']['AnswerDraftRequest'];
type Question = components['schemas']['MCQQuestion'] | components['schemas']['ClozeQuestion'] | components['schemas']['WritingQuestion'];

interface QuizRunnerProps {
  attemptId: string;
}

type SyncStatus = 'idle' | 'saving' | 'saved' | 'error' | 'conflict' | 'unknown';

interface QuestionState {
  serverRevision: number;
  serverEtag: string;
  serverAnswer: string;
  serverSelfScore: number | null;

  localAnswer: string;
  localSelfScore: number | null;

  status: SyncStatus;
  
  pendingMutation: { answer: string; selfScore: number | null; idempotencyKey: string; hasChanges: boolean } | null;
  activeMutation: { answer: string; selfScore: number | null; idempotencyKey: string; revision: number; etag: string } | null;
}

export const QuizRunner: React.FC<QuizRunnerProps> = ({ attemptId }) => {
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isRecoverable, setIsRecoverable] = useState(false);
  
  const [states, setStates] = useState<Record<string, QuestionState>>({});
  
  const unmounted = useRef(false);
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  
  useEffect(() => {
    unmounted.current = false;
    return () => { unmounted.current = true; };
  }, []);

  const loadAttempt = useCallback(async () => {
    setErrorMsg(null);
    try {
      const data = await apiClient<QuizAttempt>(`/api/v1/quiz-attempts/${encodeURIComponent(attemptId)}`, {
        cache: 'no-store'
      });
      if (unmounted.current) return;
      
      setAttempt(data);
      
      const newStates: Record<string, QuestionState> = {};
      
      for (const q of data.questions) {
        const precondition = data.answerPreconditions.find(p => p.questionId === q.id);
        const savedAnswer = data.answers.find(a => a.questionId === q.id);
        
        const serverAnswer = savedAnswer?.answer || '';
        const serverSelfScore = savedAnswer?.selfScore ?? null;
        
        newStates[q.id] = {
          serverRevision: precondition?.draftRevision ?? 0,
          serverEtag: precondition?.etag ?? '',
          serverAnswer,
          serverSelfScore,
          localAnswer: serverAnswer,
          localSelfScore: serverSelfScore,
          status: 'idle',
          pendingMutation: null,
          activeMutation: null,
        };
      }
      
      setStates(prev => {
        const merged = { ...newStates };
        for (const qId of Object.keys(prev)) {
          if (merged[qId]) {
            const p = prev[qId];
            if (p.localAnswer !== p.serverAnswer || p.localSelfScore !== p.serverSelfScore) {
              merged[qId].localAnswer = p.localAnswer;
              merged[qId].localSelfScore = p.localSelfScore;
              
              merged[qId].pendingMutation = {
                answer: p.localAnswer,
                selfScore: p.localSelfScore,
                idempotencyKey: crypto.randomUUID(),
                hasChanges: true
              };
              
              if (p.status === 'conflict') merged[qId].status = 'conflict';
            }
          }
        }
        return merged;
      });
      
    } catch (err) {
      if (unmounted.current) return;
      setIsRecoverable(true);
      if (err instanceof ApiError) {
        setErrorMsg(`Không thể tải bài kiểm tra: ${err.message}`);
      } else {
        setErrorMsg('Không thể tải bài kiểm tra. Vui lòng kiểm tra kết nối.');
      }
    }
  }, [attemptId]);

  useEffect(() => {
    loadAttempt();
  }, [loadAttempt]);

  const executeSave = async (qId: string) => {
    if (unmounted.current) return;
    
    let st: QuestionState | undefined;
    setStates(prev => {
      st = prev[qId];
      return prev;
    });
    
    if (!st || !st.pendingMutation || st.activeMutation) return;
    if (st.status === 'conflict') return;
    if (!st.pendingMutation.hasChanges && st.status !== 'unknown') {
      setStates(prev => ({
        ...prev,
        [qId]: { ...prev[qId], pendingMutation: null }
      }));
      return;
    }
    
    const mutation = {
      answer: st.pendingMutation.answer,
      selfScore: st.pendingMutation.selfScore,
      idempotencyKey: st.pendingMutation.idempotencyKey,
      revision: st.serverRevision,
      etag: st.serverEtag
    };
    
    setStates(prev => ({
      ...prev,
      [qId]: {
        ...prev[qId],
        status: 'saving',
        activeMutation: mutation,
        pendingMutation: null
      }
    }));
    
    try {
      const payload: AnswerDraftRequest = {
        answer: mutation.answer,
        draftRevision: mutation.revision,
      };
      if (mutation.selfScore !== null) {
        payload.selfScore = mutation.selfScore;
      }
      
      const response = await apiClient<Answer>(`/api/v1/quiz-attempts/${encodeURIComponent(attemptId)}/answers/${encodeURIComponent(qId)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
        headers: {
          'If-Match': mutation.etag,
          'Idempotency-Key': mutation.idempotencyKey,
        }
      });
      
      if (unmounted.current) return;
      
      // The ETag is attached as _etag non-enumerably
      const newEtag = (response as any)._etag || '';
      
      setStates(prev => {
        const cur = prev[qId];
        const nextStatus = cur.pendingMutation?.hasChanges ? 'saving' : 'saved';
        return {
          ...prev,
          [qId]: {
            ...cur,
            serverAnswer: response.answer,
            serverSelfScore: response.selfScore,
            serverRevision: response.draftRevision,
            serverEtag: newEtag,
            status: nextStatus,
            activeMutation: null,
          }
        };
      });
      
    } catch (err) {
      if (unmounted.current) return;
      
      setStates(prev => {
        const cur = prev[qId];
        let nextStatus: SyncStatus = 'error';
        
        if (err instanceof ApiError) {
          if (err.code === 'REVISION_CONFLICT') {
            nextStatus = 'conflict';
          }
        } else if (err instanceof MutationUnknownError) {
          nextStatus = 'unknown';
        }
        
        return {
          ...prev,
          [qId]: {
            ...cur,
            status: nextStatus,
            pendingMutation: cur.activeMutation ? {
              answer: cur.activeMutation.answer,
              selfScore: cur.activeMutation.selfScore,
              idempotencyKey: cur.activeMutation.idempotencyKey,
              hasChanges: true
            } : cur.pendingMutation,
            activeMutation: null,
          }
        };
      });
    }
  };
  
  useEffect(() => {
    Object.keys(states).forEach(qId => {
      const st = states[qId];
      if (st.status === 'saving' && !st.activeMutation && st.pendingMutation) {
        setTimeout(() => executeSave(qId), 0);
      }
    });
  }, [states]);

  const queueAutosave = (qId: string, answer: string, selfScore: number | null) => {
    setStates(prev => {
      const st = prev[qId];
      if (!st) return prev;
      
      const hasChanges = answer !== st.serverAnswer || selfScore !== st.serverSelfScore;
      
      const newKey = (st.pendingMutation && st.pendingMutation.answer === answer && st.pendingMutation.selfScore === selfScore) 
        ? st.pendingMutation.idempotencyKey 
        : crypto.randomUUID();
        
      return {
        ...prev,
        [qId]: {
          ...st,
          localAnswer: answer,
          localSelfScore: selfScore,
          status: st.status === 'saved' && hasChanges ? 'idle' : st.status,
          pendingMutation: {
            answer,
            selfScore,
            idempotencyKey: newKey,
            hasChanges
          }
        }
      };
    });
    
    if (debounceTimers.current[qId]) clearTimeout(debounceTimers.current[qId]);
    debounceTimers.current[qId] = setTimeout(() => {
      executeSave(qId);
    }, 500);
  };

  const handleBlur = (qId: string) => {
    if (debounceTimers.current[qId]) clearTimeout(debounceTimers.current[qId]);
    executeSave(qId);
  };

  const handleRetry = (qId: string) => {
    executeSave(qId);
  };

  if (errorMsg && !attempt) {
    return (
      <Card className="border-destructive/50 bg-destructive/10" role="alert">
        <CardHeader>
          <CardTitle className="text-destructive">Lỗi</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">{errorMsg}</p>
        </CardContent>
        {isRecoverable && (
          <div className="p-6 pt-0">
            <Button onClick={loadAttempt}>Thử lại</Button>
          </div>
        )}
      </Card>
    );
  }

  if (!attempt) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-muted-foreground" role="status" aria-live="polite">
          Đang tải bài kiểm tra...
        </CardContent>
      </Card>
    );
  }

  const isSubmitted = attempt.status === 'SUBMITTED';

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Làm bài kiểm tra</CardTitle>
        </CardHeader>
      </Card>
      
      {errorMsg && (
         <Card className="border-destructive/50 bg-destructive/10 mb-6" role="alert">
          <CardContent className="p-4 text-destructive flex flex-col sm:flex-row gap-4 justify-between items-center">
            <span>{errorMsg}</span>
            <Button size="sm" variant="outline" onClick={loadAttempt}>Tải lại dữ liệu máy chủ</Button>
          </CardContent>
         </Card>
      )}

      {attempt.questions.map((q) => {
        const st = states[q.id];
        if (!st) return null;

        return (
          <div key={q.id} className="relative">
            <QuestionRenderer
              question={q}
              answerDraft={st.localAnswer}
              selfScoreDraft={st.localSelfScore}
              onChange={(ans, score) => queueAutosave(q.id, ans, score)}
              onBlur={() => handleBlur(q.id)}
              disabled={isSubmitted}
            />
            {!isSubmitted && (
              <div className="absolute top-4 right-4 flex items-center space-x-2 text-sm" aria-live="polite">
                {st.status === 'saving' && <span className="text-muted-foreground">Đang lưu...</span>}
                {st.status === 'saved' && <span className="text-primary font-medium">Đã lưu</span>}
                {st.status === 'error' && (
                  <span className="text-destructive flex items-center gap-2 bg-background p-1 rounded">
                    Lỗi lưu
                    <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={() => handleRetry(q.id)}>Thử lại</Button>
                  </span>
                )}
                {st.status === 'unknown' && (
                  <span className="text-destructive flex items-center gap-2 bg-background p-1 rounded">
                    Chưa rõ kết quả
                    <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={() => handleRetry(q.id)}>Kiểm tra lại</Button>
                  </span>
                )}
                {st.status === 'conflict' && (
                  <span className="text-destructive flex items-center gap-2 bg-background p-1 rounded">
                    Xung đột phiên bản
                    <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={loadAttempt}>Tải lại</Button>
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}

      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-muted-foreground mb-4">
            Tính năng nộp bài (submission) chưa được tích hợp. Bài làm sẽ được tự động lưu.
          </p>
          <Button disabled className="w-full sm:w-auto">Nộp bài (Chưa khả dụng)</Button>
        </CardContent>
      </Card>
    </div>
  );
};
