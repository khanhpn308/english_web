import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useAiConsent } from '@/features/consent/AiConsentGate';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';

type WritingQuestion = components['schemas']['WritingQuestion'];

export interface FeedbackCriterion {
  criterion: 'TARGET_WORD_USAGE' | 'GRAMMAR' | 'CLARITY' | string;
  commentVi: string;
}

export interface Feedback {
  feedbackId: string;
  attemptId: string;
  questionId: string;
  answerRevision: number;
  status: 'REQUESTED' | 'VALIDATED' | 'FAILED';
  summaryVi?: string;
  criteria?: FeedbackCriterion[];
  provider?: string;
  model?: string;
  promptVersion?: string;
  errorCategory?: string | null;
  operationId: string;
  retryOfOperationId?: string | null;
  createdAt: string;
  updatedAt?: string;
}

export interface FeedbackPage {
  data: Feedback[];
  pagination: {
    nextCursor: string | null;
    pageSize: number;
    hasMore: boolean;
  };
}

export interface FeedbackRequest {
  rubricVersion: string;
  answerRevision: number;
  retryOfOperationId?: string;
}

export interface FeedbackPanelProps {
  attemptId: string;
  question: WritingQuestion;
  savedAnswer: string;
  answerRevision: number;
  selfScore: number;
}

const CRITERION_LABELS: Record<string, string> = {
  TARGET_WORD_USAGE: 'Sử dụng từ vựng mục tiêu',
  GRAMMAR: 'Ngữ pháp',
  CLARITY: 'Độ rõ ràng và mạch lạc',
};

export const FeedbackPanel: React.FC<FeedbackPanelProps> = ({
  attemptId,
  question,
  savedAnswer,
  answerRevision,
  selfScore,
}) => {
  const consent = useAiConsent();
  const [history, setHistory] = useState<Feedback[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [isRequesting, setIsRequesting] = useState(false);
  const [isReconciling, setIsReconciling] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [unknownIntent, setUnknownIntent] = useState<{ key: string; body: FeedbackRequest } | null>(null);
  const [showHistoryList, setShowHistoryList] = useState(false);

  const alive = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  const requestLock = useRef(false);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const loadHistory = useCallback(
    async (cursor?: string): Promise<boolean> => {
      if (!alive.current) return false;
      setLoadingHistory(true);
      try {
        const params: Record<string, string> = {
          attemptId,
          pageSize: '10',
        };
        if (cursor) {
          params.cursor = cursor;
        }

        const response = await apiClient<FeedbackPage>(
          `/api/v1/quiz-questions/${encodeURIComponent(question.id)}/feedback`,
          {
            params,
            cache: 'no-store',
          }
        );

        if (!alive.current) return false;
        if (response && Array.isArray(response.data) && response.pagination) {
          setHistory((prev) => (cursor ? [...prev, ...response.data] : response.data));
          setHistoryCursor(response.pagination?.nextCursor ?? null);
          setHistoryHasMore(Boolean(response.pagination.hasMore));
          return true;
        }
        return false;
      } catch {
        // Preserve acknowledged history and all unresolved mutation identity.
        return false;
      } finally {
        if (alive.current) {
          setLoadingHistory(false);
        }
      }
    },
    [attemptId, question.id]
  );

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const latestFeedback = history[0] || null;

  const handleRequestFeedback = useCallback(
    async (explicitRetryOpId?: string, replay?: { key: string; body: FeedbackRequest }) => {
      // A possibly dispatched request is never replaced by a fresh key until resolved.
      if (requestLock.current || isRequesting || isReconciling || (unknownIntent && !replay)) return;
      requestLock.current = true;
      setErrorMessage(null);
      setStatusMessage(null);

      // Same-key replay must use the exact original body/fingerprint.
      const targetRetryOpId = replay
        ? replay.body.retryOfOperationId
        : explicitRetryOpId ?? (latestFeedback?.status === 'FAILED' ? latestFeedback.operationId : undefined);

      // Granting consent must not dispatch automatically.
      let authorizedCallbackStarted = false;
      try {
      await consent.requestPermission(async () => {
        authorizedCallbackStarted = true;
        if (!alive.current) return;
        setIsRequesting(true);
        setStatusMessage('Đang gửi yêu cầu nhận xét tới AI bridge...');

        const idempotencyKey = replay?.key ?? crypto.randomUUID();
        const controller = new AbortController();
        abortRef.current = controller;
        const timeoutId = setTimeout(() => controller.abort(), 30_000); // 30s deadline per contract

        const body: FeedbackRequest = replay?.body ?? {
          rubricVersion: question.rubricVersion,
          answerRevision,
          ...(targetRetryOpId ? { retryOfOperationId: targetRetryOpId } : {}),
        };

        try {
          const result = await apiClient<Feedback>(
            `/api/v1/quiz-questions/${encodeURIComponent(question.id)}/feedback`,
            {
              method: 'POST',
              body: JSON.stringify(body),
              headers: {
                'Idempotency-Key': idempotencyKey,
              },
              signal: controller.signal,
            }
          );

          if (!alive.current) return;
          setUnknownIntent(null);

          if (result && result.feedbackId) {
            setHistory((prev) => [result, ...prev.filter((f) => f.feedbackId !== result.feedbackId)]);
            if (result.status === 'VALIDATED') {
              setStatusMessage('Nhận xét từ AI đã hoàn tất.');
            } else if (result.status === 'FAILED') {
              setErrorMessage(
                `Yêu cầu nhận xét không thành công (${result.errorCategory || 'Lỗi xử lý'}). Bạn có thể thử lại.`
              );
            } else {
              setStatusMessage('Yêu cầu nhận xét đã được tiếp nhận và đang xử lý.');
            }
          }
        } catch (err) {
          if (!alive.current) return;
          setStatusMessage(null);

          if (err instanceof DOMException && err.name === 'AbortError') {
            setErrorMessage('Yêu cầu nhận xét vượt quá thời gian chờ (30 giây). Hãy kiểm tra lại sau.');
            setUnknownIntent({ key: idempotencyKey, body });
          } else if (err instanceof MutationUnknownError) {
            setErrorMessage('Chưa xác định kết quả nhận xét từ AI. Hãy kiểm tra kết quả trước khi gửi lại.');
            setUnknownIntent({ key: idempotencyKey, body });
          } else if (err instanceof ApiError) {
            if (err.code === 'AI_CONSENT_REQUIRED') {
              setErrorMessage('Quyền gửi dữ liệu AI đã bị thu hồi hoặc hết hạn. Vui lòng kiểm tra lại quyền.');
              void consent.refresh();
            } else if (err.code === 'BRIDGE_UNAVAILABLE' || err.code === 'NETWORK_REQUIRED') {
              setErrorMessage('AI bridge hoặc kết nối mạng hiện không sẵn sàng. Điểm tự chấm của bạn được bảo toàn.');
            } else if (err.code === 'BRIDGE_AUTH_ERROR') {
              setErrorMessage('Lỗi xác thực với AI bridge. Vui lòng kiểm tra cấu hình hệ thống.');
            } else if (err.code === 'IDEMPOTENCY_IN_FLIGHT') {
              setErrorMessage('Một yêu cầu nhận xét đang được xử lý. Vui lòng đợi.');
              setUnknownIntent({ key: idempotencyKey, body });
            } else {
              setErrorMessage(`Lỗi yêu cầu nhận xét (${err.code}): ${err.message}`);
            }
          } else {
            setErrorMessage('Không thể gửi yêu cầu nhận xét AI. Kiểm tra API cục bộ và thử lại.');
          }
        } finally {
          clearTimeout(timeoutId);
          abortRef.current = null;
          requestLock.current = false;
          if (alive.current) {
            setIsRequesting(false);
          }
        }
      });
      } finally {
        // Consent was absent: no callback and no AI dispatch.
        if (!authorizedCallbackStarted) requestLock.current = false;
      }
    },
    [answerRevision, consent, isReconciling, isRequesting, latestFeedback, question.id, question.rubricVersion, unknownIntent]
  );

  const handleReconcile = useCallback(async () => {
    if (isReconciling) return;
    setIsReconciling(true);
    setStatusMessage('Đang kiểm tra kết quả nhận xét từ máy chủ...');
    setErrorMessage(null);
    try {
      const loaded = await loadHistory();
      if (!alive.current) return;
      if (!loaded) {
        setErrorMessage('Không tải được lịch sử. Kết quả yêu cầu trước vẫn chưa xác định.');
        return;
      }
      // History alone cannot prove the idempotency identity of a lost response.
      // Keep the original key/body for an explicit same-intent replay.
      setStatusMessage('Đã tải lịch sử. Nếu yêu cầu trước chưa được xác nhận, hãy tiếp tục bằng cùng khóa.');
    } catch {
      if (!alive.current) return;
      setErrorMessage('Không thể đối soát kết quả. Bạn có thể kiểm tra lại sau.');
    } finally {
      if (alive.current) {
        setIsReconciling(false);
      }
    }
  }, [isReconciling, loadHistory]);

  const isAnswerBlank = !savedAnswer.trim();
  const isValidated = latestFeedback?.status === 'VALIDATED';
  const isFailed = latestFeedback?.status === 'FAILED';
  const isPendingProcessing = latestFeedback?.status === 'REQUESTED';

  return (
    <Card className="mt-4 border-muted-foreground/20 bg-muted/20" role="region" aria-label="Nhận xét AI cho câu viết">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center justify-between flex-wrap gap-2">
          <span>Hỗ trợ nhận xét AI (Tự luận)</span>
          <span className="text-xs font-normal text-muted-foreground">
            Bản nháp số #{answerRevision} · Điểm tự chấm: {selfScore}/4
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Canonical Answer & Score confirmation */}
        <div className="bg-background p-3 rounded-md border border-border text-sm space-y-1">
          <p className="font-medium text-foreground">Câu viết đã nộp:</p>
          <p className="italic text-foreground whitespace-pre-wrap break-words">
            {savedAnswer || '(Chưa có nội dung viết)'}
          </p>
        </div>

        {/* Action Button & Instructions */}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant={isFailed ? 'outline' : 'default'}
            size="sm"
            disabled={
              isRequesting ||
              isReconciling ||
              Boolean(unknownIntent) ||
              consent.pending ||
              Boolean(consent.unresolved) ||
              isAnswerBlank ||
              isValidated ||
              isPendingProcessing
            }
            onClick={() => void handleRequestFeedback()}
          >
            {isRequesting
              ? 'Đang gửi yêu cầu...'
              : isPendingProcessing
              ? 'Đang chờ nhận xét...'
              : isValidated
              ? 'Đã có nhận xét AI'
              : isFailed
              ? 'Thử lại nhận xét AI'
              : 'Yêu cầu AI nhận xét'}
          </Button>

          {unknownIntent && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isReconciling || isRequesting}
                onClick={() => void handleReconcile()}
              >
                {isReconciling ? 'Đang đối soát...' : 'Kiểm tra kết quả nhận xét'}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isReconciling || isRequesting || consent.pending}
                onClick={() => void handleRequestFeedback(undefined, unknownIntent)}
              >
                Tiếp tục yêu cầu cũ (cùng khóa)
              </Button>
            </>
          )}

          <span className="text-xs text-muted-foreground">
            Nhận xét AI là tùy chọn, không bắt buộc và không thay đổi điểm tự chấm của bạn.
          </span>
        </div>

        {/* Status and Error announcements */}
        {statusMessage && (
          <p className="text-sm text-primary font-medium" role="status" aria-live="polite">
            {statusMessage}
          </p>
        )}

        {errorMessage && (
          <p className="text-sm text-destructive font-medium" role="alert" aria-live="assertive">
            {errorMessage}
          </p>
        )}

        {/* Latest Feedback display */}
        {latestFeedback && (
          <div className="bg-background p-4 rounded-md border border-border space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2 text-sm border-b border-border pb-2">
              <span className="font-semibold flex items-center">
                Nhận xét gần nhất
                <span
                  className={cn(
                    'ml-2 px-2 py-0.5 rounded text-xs font-semibold',
                    latestFeedback.status === 'VALIDATED' &&
                      'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
                    latestFeedback.status === 'FAILED' &&
                      'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
                    latestFeedback.status === 'REQUESTED' &&
                      'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                  )}
                >
                  {latestFeedback.status === 'VALIDATED' && 'Đã nhận xét'}
                  {latestFeedback.status === 'FAILED' && 'Thất bại'}
                  {latestFeedback.status === 'REQUESTED' && 'Đang xử lý'}
                </span>
              </span>
              <span className="text-xs text-muted-foreground">
                {new Date(latestFeedback.createdAt).toLocaleString('vi-VN')}
              </span>
            </div>

            {latestFeedback.status === 'VALIDATED' && (
              <div className="space-y-3 text-sm">
                {latestFeedback.summaryVi && (
                  <div>
                    <p className="font-semibold text-foreground">Tổng quan:</p>
                    <p className="text-muted-foreground whitespace-pre-wrap break-words mt-1">
                      {latestFeedback.summaryVi}
                    </p>
                  </div>
                )}

                {Array.isArray(latestFeedback.criteria) && latestFeedback.criteria.length > 0 && (
                  <div className="space-y-2">
                    <p className="font-semibold text-foreground">Chi tiết tiêu chí:</p>
                    <ul className="list-disc pl-5 space-y-1.5 text-muted-foreground">
                      {latestFeedback.criteria.map((crit, idx) => (
                        <li key={idx}>
                          <span className="font-semibold text-foreground">
                            {CRITERION_LABELS[crit.criterion] || crit.criterion}:
                          </span>{' '}
                          {crit.commentVi}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(latestFeedback.provider || latestFeedback.model) && (
                  <p className="text-xs text-muted-foreground pt-2 border-t border-border">
                    Mô hình: {latestFeedback.provider || 'AI'} · {latestFeedback.model || ''}
                  </p>
                )}
              </div>
            )}

            {latestFeedback.status === 'FAILED' && (
              <div className="space-y-2 text-sm">
                <p className="text-destructive font-medium">
                  Nhận xét không thành công ({latestFeedback.errorCategory || 'Lỗi không xác định'}).
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isRequesting || isReconciling}
                  onClick={() => void handleRequestFeedback(latestFeedback.operationId)}
                >
                  Thử lại nhận xét (Yêu cầu mới)
                </Button>
              </div>
            )}

            {latestFeedback.status === 'REQUESTED' && (
              <p className="text-sm text-muted-foreground">
                Yêu cầu đang chờ xử lý từ AI bridge. Vui lòng kiểm tra lại sau giây lát.
              </p>
            )}
          </div>
        )}

        {/* History records list */}
        {history.length > 1 && (
          <div className="space-y-2 pt-2 border-t border-border">
            <button
              type="button"
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring rounded-sm"
              onClick={() => setShowHistoryList((v) => !v)}
              aria-expanded={showHistoryList}
            >
              {showHistoryList ? 'Ẩn lịch sử nhận xét' : `Xem lịch sử nhận xét (${history.length} lần)`}
            </button>

            {showHistoryList && (
              <div className="space-y-3 pt-2">
                {history.slice(1).map((item) => (
                  <div
                    key={item.feedbackId}
                    className="p-3 rounded-md border border-border bg-background text-xs space-y-1.5"
                  >
                    <div className="flex justify-between items-center text-muted-foreground">
                      <span>{new Date(item.createdAt).toLocaleString('vi-VN')}</span>
                      <span
                        className={cn(
                          'font-semibold px-1.5 py-0.5 rounded text-[10px]',
                          item.status === 'VALIDATED' &&
                            'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
                          item.status === 'FAILED' &&
                            'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
                          item.status === 'REQUESTED' &&
                            'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                        )}
                      >
                        {item.status === 'VALIDATED' && 'ĐÃ NHẬN XÉT'}
                        {item.status === 'FAILED' && 'THẤT BẠI'}
                        {item.status === 'REQUESTED' && 'ĐANG XỬ LÝ'}
                      </span>
                    </div>
                    {item.summaryVi && <p className="text-foreground">{item.summaryVi}</p>}
                    {item.status === 'FAILED' && (
                      <div className="pt-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => void handleRequestFeedback(item.operationId)}
                        >
                          Thử lại
                        </Button>
                      </div>
                    )}
                  </div>
                ))}

                {historyHasMore && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    disabled={loadingHistory}
                    onClick={() => void loadHistory(historyCursor ?? undefined)}
                  >
                    {loadingHistory ? 'Đang tải...' : 'Tải thêm lịch sử'}
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
