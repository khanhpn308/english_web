import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useAiConsent } from '@/features/consent/AiConsentGate';
import { ApiError, MutationUnknownError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';

type WritingQuestion = components['schemas']['WritingQuestion'];

export interface FeedbackCriterion {
  criterion: string;
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
  const [unknownIntent, setUnknownIntent] = useState<{ key: string; retryOpId?: string } | null>(null);
  const [showHistoryList, setShowHistoryList] = useState(false);

  const alive = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const loadHistory = useCallback(async (cursor?: string) => {
    if (!alive.current) return;
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

      if (!alive.current) return;
      if (response && Array.isArray(response.data)) {
        setHistory((prev) => (cursor ? [...prev, ...response.data] : response.data));
        setHistoryCursor(response.pagination?.nextCursor ?? null);
        setHistoryHasMore(Boolean(response.pagination?.hasMore));
      }
    } catch {
      // If endpoint is not yet integrated on backend (CASE B: DEFERRED_DEPENDENCY),
      // we maintain empty history without crashing.
    } finally {
      if (alive.current) {
        setLoadingHistory(false);
      }
    }
  }, [attemptId, question.id]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleRequestFeedback = useCallback(async (retryOpId?: string) => {
    if (isRequesting || isReconciling) return;
    setErrorMessage(null);
    setStatusMessage(null);

    // Consent gate: checked before every request.
    // Granting consent does NOT auto-dispatch; user must click again after grant.
    await consent.requestPermission(async () => {
      if (!alive.current) return;
      setIsRequesting(true);
      setStatusMessage('Đang gửi yêu cầu nhận xét tới AI bridge...');

      const idempotencyKey = crypto.randomUUID();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 30_000); // 30s deadline per contract

      const body: FeedbackRequest = {
        rubricVersion: question.rubricVersion || 'writing-rubric-v1',
        answerRevision,
        ...(retryOpId ? { retryOfOperationId: retryOpId } : {}),
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
          setUnknownIntent({ key: idempotencyKey, retryOpId });
        } else if (err instanceof MutationUnknownError) {
          setErrorMessage('Chưa xác định kết quả nhận xét từ AI. Hãy kiểm tra kết quả trước khi gửi lại.');
          setUnknownIntent({ key: idempotencyKey, retryOpId });
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
            setUnknownIntent({ key: idempotencyKey, retryOpId });
          } else {
            setErrorMessage(`Lỗi yêu cầu nhận xét (${err.code}): ${err.message}`);
          }
        } else {
          setErrorMessage('Không thể gửi yêu cầu nhận xét AI. Kiểm tra API cục bộ và thử lại.');
        }
      } finally {
        clearTimeout(timeoutId);
        abortRef.current = null;
        if (alive.current) {
          setIsRequesting(false);
        }
      }
    });
  }, [answerRevision, consent, isReconciling, isRequesting, question.id, question.rubricVersion]);

  const handleReconcile = useCallback(async () => {
    if (isReconciling) return;
    setIsReconciling(true);
    setStatusMessage('Đang kiểm tra kết quả nhận xét từ máy chủ...');
    setErrorMessage(null);
    try {
      await loadHistory();
      if (!alive.current) return;
      setUnknownIntent(null);
      setStatusMessage('Đã cập nhật trạng thái nhận xét từ máy chủ.');
    } catch {
      if (!alive.current) return;
      setErrorMessage('Không thể đối soát kết quả. Bạn có thể kiểm tra lại sau.');
    } finally {
      if (alive.current) {
        setIsReconciling(false);
      }
    }
  }, [isReconciling, loadHistory]);

  const latestFeedback = history[0] || null;

  return (
    <Card className="mt-4 border-muted-foreground/20 bg-muted/30" role="region" aria-label="Nhận xét AI cho câu viết">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center justify-between flex-wrap gap-2">
          <span>Hỗ trợ nhận xét AI (Tự luận)</span>
          <span className="text-xs font-normal text-muted-foreground">
            Bản nháp số {answerRevision} · Điểm tự chấm: {selfScore}/4
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Canonical Answer & Score display */}
        <div className="bg-background/80 p-3 rounded-md border border-border text-sm space-y-1">
          <p className="font-medium text-foreground">Câu viết đã nộp:</p>
          <p className="italic text-foreground whitespace-pre-wrap break-words">
            {savedAnswer || '(Chưa có nội dung viết)'}
          </p>
        </div>

        {/* Action Button & Instructions */}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="default"
            size="sm"
            disabled={
              isRequesting ||
              isReconciling ||
              consent.pending ||
              Boolean(consent.unresolved) ||
              !savedAnswer.trim()
            }
            onClick={() => void handleRequestFeedback()}
          >
            {isRequesting ? 'Đang gửi yêu cầu...' : 'Yêu cầu AI nhận xét'}
          </Button>

          {unknownIntent && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isReconciling}
              onClick={() => void handleReconcile()}
            >
              {isReconciling ? 'Đang đối soát...' : 'Kiểm tra kết quả nhận xét'}
            </Button>
          )}

          <span className="text-xs text-muted-foreground">
            Nhận xét AI là tùy chọn và không thay đổi điểm tự chấm của bạn.
          </span>
        </div>

        {/* Status and Error announcements */}
        {statusMessage && (
          <p className="text-sm text-primary" role="status" aria-live="polite">
            {statusMessage}
          </p>
        )}

        {errorMessage && (
          <p className="text-sm text-destructive" role="alert" aria-live="assertive">
            {errorMessage}
          </p>
        )}

        {/* Latest Feedback display */}
        {latestFeedback && (
          <div className="bg-background p-4 rounded-md border border-border space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2 text-sm border-b border-border pb-2">
              <span className="font-semibold">
                Nhận xét gần nhất
                <span
                  className={cn(
                    'ml-2 px-2 py-0.5 rounded text-xs font-medium',
                    latestFeedback.status === 'VALIDATED' && 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300',
                    latestFeedback.status === 'FAILED' && 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
                    latestFeedback.status === 'REQUESTED' && 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
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
                    <p className="font-medium text-foreground">Tổng quan:</p>
                    <p className="text-muted-foreground whitespace-pre-wrap break-words">
                      {latestFeedback.summaryVi}
                    </p>
                  </div>
                )}

                {Array.isArray(latestFeedback.criteria) && latestFeedback.criteria.length > 0 && (
                  <div className="space-y-2">
                    <p className="font-medium text-foreground">Chi tiết tiêu chí:</p>
                    <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                      {latestFeedback.criteria.map((crit, idx) => (
                        <li key={idx}>
                          <span className="font-semibold text-foreground">{crit.criterion}:</span>{' '}
                          {crit.commentVi}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(latestFeedback.provider || latestFeedback.model) && (
                  <p className="text-xs text-muted-foreground pt-1 border-t border-border">
                    Mô hình: {latestFeedback.provider || 'AI'} · {latestFeedback.model || ''}
                  </p>
                )}
              </div>
            )}

            {latestFeedback.status === 'FAILED' && (
              <div className="space-y-2 text-sm">
                <p className="text-destructive">
                  Nhận xét không thành công ({latestFeedback.errorCategory || 'Lỗi không xác định'}).
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isRequesting || isReconciling}
                  onClick={() => void handleRequestFeedback(latestFeedback.feedbackId)}
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
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
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
                    className="p-3 rounded border border-border bg-background text-xs space-y-1"
                  >
                    <div className="flex justify-between items-center text-muted-foreground">
                      <span>{new Date(item.createdAt).toLocaleString('vi-VN')}</span>
                      <span>Trạng thái: {item.status}</span>
                    </div>
                    {item.summaryVi && <p className="text-foreground">{item.summaryVi}</p>}
                    {item.status === 'FAILED' && (
                      <div className="pt-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => void handleRequestFeedback(item.feedbackId)}
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
