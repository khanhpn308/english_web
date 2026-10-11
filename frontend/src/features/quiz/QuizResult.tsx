import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ApiError, apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';
import { FeedbackPanel } from './FeedbackPanel';

type QuizAttempt = components['schemas']['QuizAttempt'];
type QuizResultData = components['schemas']['QuizResult'];
type PublicQuestion = components['schemas']['QuizAttempt']['questions'][number];
type WritingQuestion = components['schemas']['WritingQuestion'];

export interface QuizResultProps {
  attemptId: string;
  onNavigate?: (path: string) => void;
}

function ratingLabel(rating: string): string {
  switch (rating) {
    case 'AGAIN':
      return 'Cần học lại (Again)';
    case 'HARD':
      return 'Khó (Hard)';
    case 'GOOD':
      return 'Tốt (Good)';
    case 'EASY':
      return 'Dễ (Easy)';
    default:
      return rating;
  }
}

export const QuizResult: React.FC<QuizResultProps> = ({ attemptId, onNavigate }) => {
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchAttempt = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const data = await apiClient<QuizAttempt>(
        `/api/v1/quiz-attempts/${encodeURIComponent(attemptId)}`,
        { cache: 'no-store' }
      );
      if (!data || data.id !== attemptId) {
        throw new Error('Dữ liệu bài kiểm tra không hợp lệ');
      }
      setAttempt(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'QUIZ_RESTORE_REQUIRED') {
          setErrorMessage('Bài kiểm tra cần khôi phục lại từ máy chủ. Vui lòng tải lại.');
        } else {
          setErrorMessage(`Lỗi tải kết quả (${err.code}): ${err.message}`);
        }
      } else {
        setErrorMessage('Không thể tải bài kiểm tra. Vui lòng kiểm tra API cục bộ hoặc phiên làm việc.');
      }
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    void fetchAttempt();
  }, [fetchAttempt]);

  const handleNavigate = (path: string) => {
    if (onNavigate) {
      onNavigate(path);
    } else if (typeof window !== 'undefined') {
      window.location.assign(path);
    }
  };

  // State 1: Loading
  if (loading && !attempt) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground" role="status">
            Đang tải kết quả bài kiểm tra...
          </CardContent>
        </Card>
      </div>
    );
  }

  // State 2: Error
  if (errorMessage && !attempt) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Card className="border-destructive/50 bg-destructive/5" role="alert">
          <CardHeader>
            <CardTitle className="text-destructive text-lg">Lỗi tải kết quả bài kiểm tra</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-foreground">{errorMessage}</p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => void fetchAttempt()} variant="default" size="sm">
                Thử lại
              </Button>
              <Button onClick={() => handleNavigate('/')} variant="outline" size="sm">
                Về trang chủ
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // State 3: In Progress (result is null, attempt not yet submitted)
  if (attempt && attempt.status === 'IN_PROGRESS') {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle className="text-xl">Bài kiểm tra chưa hoàn thành</CardTitle>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                Đang làm dở
              </span>
            </div>
            <CardDescription>
              Bài kiểm tra này chưa được nộp. Bạn cần hoàn thành và nộp bài để xem điểm số và nhận xét.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Tiến độ hiện tại: đã lưu nháp {attempt.savedAnswerCount} câu trả lời.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => handleNavigate(`/quiz/${encodeURIComponent(attemptId)}`)} variant="default">
                Tiếp tục làm bài
              </Button>
              <Button onClick={() => handleNavigate('/')} variant="outline">
                Về trang chủ
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const result: QuizResultData | null = attempt?.result ?? null;

  // State 4: Submitted but missing result
  if (!result) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Card className="border-destructive/50 bg-destructive/5" role="alert">
          <CardHeader>
            <CardTitle className="text-destructive text-lg">Chưa có kết quả nộp bài</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-foreground">
              Không tìm thấy dữ liệu kết quả bài kiểm tra đã nộp. Vui lòng kiểm tra lại.
            </p>
            <Button onClick={() => void fetchAttempt()} variant="outline" size="sm">
              Tải lại
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { mcq, cloze } = result.objectiveScores;
  const questions: PublicQuestion[] = attempt?.questions ?? [];
  const answers = attempt?.answers ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* SECTION 1 — HEADER */}
      <Card>
        <CardHeader>
          <div className="flex items-start sm:items-center justify-between flex-wrap gap-3">
            <div>
              <CardTitle className="text-2xl font-bold">Kết quả bài kiểm tra</CardTitle>
              <CardDescription className="mt-1">
                Thời gian nộp: {new Date(result.submittedAt).toLocaleString('vi-VN')} · Bản nộp: #{result.submissionRevision}
              </CardDescription>
            </div>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
              Đã nộp bài
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => handleNavigate('/quiz/new')} variant="default" size="sm">
              Làm bài kiểm tra mới
            </Button>
            <Button onClick={() => handleNavigate('/')} variant="outline" size="sm">
              Về trang chủ
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* SECTION 2 — OBJECTIVE PERFORMANCE */}
      <section aria-labelledby="objective-scores-heading" className="space-y-4">
        <h2 id="objective-scores-heading" className="text-xl font-bold text-foreground">
          Điểm câu hỏi khách quan
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* MCQ Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center justify-between">
                <span>Trắc nghiệm (MCQ)</span>
                <span className="text-lg font-bold text-primary">
                  {mcq.accuracy !== null ? `${Math.round(mcq.accuracy * 100)}%` : '—'}
                </span>
              </CardTitle>
              <CardDescription>
                Đúng {mcq.correct} / {mcq.attempted} câu đã làm (Tổng: {mcq.total} câu)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="w-full bg-secondary rounded-full h-2.5 overflow-hidden"
                role="progressbar"
                aria-valuenow={mcq.accuracy !== null ? Math.round(mcq.accuracy * 100) : 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Độ chính xác trắc nghiệm MCQ"
              >
                <div
                  className="bg-primary h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${mcq.accuracy !== null ? Math.round(mcq.accuracy * 100) : 0}%` }}
                />
              </div>
            </CardContent>
          </Card>

          {/* CLOZE Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center justify-between">
                <span>Điền từ (CLOZE)</span>
                <span className="text-lg font-bold text-primary">
                  {cloze.accuracy !== null ? `${Math.round(cloze.accuracy * 100)}%` : '—'}
                </span>
              </CardTitle>
              <CardDescription>
                Đúng {cloze.correct} / {cloze.attempted} câu đã làm (Tổng: {cloze.total} câu)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="w-full bg-secondary rounded-full h-2.5 overflow-hidden"
                role="progressbar"
                aria-valuenow={cloze.accuracy !== null ? Math.round(cloze.accuracy * 100) : 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Độ chính xác điền từ CLOZE"
              >
                <div
                  className="bg-primary h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${cloze.accuracy !== null ? Math.round(cloze.accuracy * 100) : 0}%` }}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* SECTION 3 & 4 — DETAILED QUESTION RESULTS & WRITING SELF-SCORE */}
      <section aria-labelledby="question-results-heading" className="space-y-4">
        <h2 id="question-results-heading" className="text-xl font-bold text-foreground">
          Chi tiết kết quả từng câu
        </h2>
        <div className="space-y-6">
          {questions.map((question, index) => {
            const ans = answers.find((a) => a.questionId === question.id);
            const qResult = result.questionResults.find((r) => r.questionId === question.id);

            return (
              <Card key={question.id} className="border-border">
                <CardHeader className="pb-3">
                  <div className="flex items-start sm:items-center justify-between flex-wrap gap-2">
                    <span className="font-semibold text-base text-foreground">
                      Câu {index + 1}:{' '}
                      {question.type === 'MCQ' && 'Trắc nghiệm (MCQ)'}
                      {question.type === 'CLOZE' && 'Điền từ (CLOZE)'}
                      {question.type === 'WRITING' && 'Tự luận (WRITING)'}
                    </span>

                    {/* Status Badge */}
                    {question.type === 'WRITING' ? (
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                          Điểm tự chấm: {ans?.selfScore ?? '—'}/4
                        </span>
                        {qResult?.type === 'WRITING' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">
                            {ratingLabel(qResult.rating)}
                          </span>
                        )}
                      </div>
                    ) : (
                      <div>
                        {qResult?.outcome === 'CORRECT' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            Đúng
                          </span>
                        )}
                        {qResult?.outcome === 'INCORRECT' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
                            Sai
                          </span>
                        )}
                        {qResult?.outcome === 'BLANK' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            Chưa trả lời
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Prompt */}
                  <div className="bg-muted/30 p-3 rounded-md border border-border">
                    <p className="font-medium text-foreground">{question.promptEn}</p>
                  </div>

                  {/* MCQ specific presentation */}
                  {question.type === 'MCQ' && (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Các lựa chọn:
                      </p>
                      <div className="space-y-1.5">
                        {question.options.map((option) => {
                          const isUserChoice = ans?.answer === option.id;
                          const isCorrectChoice =
                            qResult?.type === 'MCQ' && qResult.correctOptionId === option.id;

                          return (
                            <div
                              key={option.id}
                              className={cn(
                                'p-3 rounded-md border text-sm flex items-center justify-between transition-colors',
                                isCorrectChoice &&
                                  'border-emerald-500 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200 font-medium',
                                isUserChoice &&
                                  !isCorrectChoice &&
                                  'border-destructive bg-destructive/10 text-destructive',
                                !isUserChoice && !isCorrectChoice && 'border-border bg-background text-foreground'
                              )}
                            >
                              <span>{option.textEn}</span>
                              <span className="text-xs font-medium">
                                {isCorrectChoice && '✓ Đáp án đúng'}
                                {isUserChoice && !isCorrectChoice && '✗ Lựa chọn của bạn'}
                              </span>
                            </div>
                          );
                        })}
                      </div>

                      {qResult?.type === 'MCQ' && qResult.explanationVi && (
                        <div className="mt-3 p-3 rounded-md bg-muted/50 border border-border text-sm space-y-1">
                          <p className="font-semibold text-foreground">Giải thích (Tiếng Việt):</p>
                          <p className="text-muted-foreground whitespace-pre-wrap">{qResult.explanationVi}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* CLOZE specific presentation */}
                  {question.type === 'CLOZE' && (
                    <div className="space-y-3 text-sm">
                      <div className="p-3 rounded-md border border-border bg-background">
                        <span className="text-muted-foreground font-medium">Câu trả lời của bạn: </span>
                        <span
                          className={cn(
                            'font-semibold',
                            qResult?.outcome === 'CORRECT' && 'text-emerald-700 dark:text-emerald-400',
                            qResult?.outcome === 'INCORRECT' && 'text-destructive',
                            qResult?.outcome === 'BLANK' && 'text-muted-foreground italic'
                          )}
                        >
                          {ans?.answer ? ans.answer : '(Để trống)'}
                        </span>
                      </div>

                      {qResult?.type === 'CLOZE' && qResult.acceptedAnswers && (
                        <div className="p-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200">
                          <span className="font-semibold">Đáp án được chấp nhận: </span>
                          <span>{qResult.acceptedAnswers.join(' / ')}</span>
                        </div>
                      )}

                      {qResult?.type === 'CLOZE' && qResult.explanationVi && (
                        <div className="p-3 rounded-md bg-muted/50 border border-border space-y-1">
                          <p className="font-semibold text-foreground">Giải thích (Tiếng Việt):</p>
                          <p className="text-muted-foreground whitespace-pre-wrap">{qResult.explanationVi}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* WRITING specific presentation */}
                  {question.type === 'WRITING' && (
                    <div className="space-y-4">
                      <div className="p-3 rounded-md border border-border bg-background text-sm">
                        <p className="font-medium text-foreground">Từ vựng mục tiêu: <span className="font-semibold text-primary">{question.targetLemma}</span></p>
                        <div className="mt-2 pt-2 border-t border-border">
                          <p className="font-medium text-foreground">Câu viết đã nộp:</p>
                          <p className="italic text-foreground whitespace-pre-wrap break-words mt-1">
                            {ans?.answer || '(Chưa có nội dung viết)'}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 p-3 rounded-md bg-muted/40 border border-border text-sm">
                        <div>
                          <span className="font-medium text-foreground">Điểm tự chấm: </span>
                          <span className="font-bold text-primary">{ans?.selfScore ?? '—'} / 4</span>
                        </div>
                        {qResult?.type === 'WRITING' && qResult.rating && (
                          <div className="border-l border-border pl-3">
                            <span className="text-muted-foreground">Đánh giá hệ thống: </span>
                            <span className="font-medium text-foreground">{ratingLabel(qResult.rating)}</span>
                          </div>
                        )}
                      </div>

                      {question.rubric?.descriptors && (
                        <div className="text-xs text-muted-foreground">
                          {question.rubric.descriptors.find((d) => d.score === (ans?.selfScore ?? '—'))?.textVi && (
                            <p className="italic">
                              Mô tả mức điểm {ans?.selfScore ?? '—'}/4:{' '}
                              {question.rubric.descriptors.find((d) => d.score === (ans?.selfScore ?? '—'))?.textVi}
                            </p>
                          )}
                        </div>
                      )}

                      {/* SECTION 6 — AI WRITING FEEDBACK */}
                      {ans && ans.selfScore !== null && ans.selfScore !== undefined &&
                        ans.draftRevision >= 1 && (
                        <FeedbackPanel
                          attemptId={attemptId}
                          question={question as WritingQuestion}
                          savedAnswer={ans.answer}
                          answerRevision={ans.draftRevision}
                          selfScore={ans.selfScore}
                        />
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* SECTION 5 — SRS HANDOFF PRESENTATION */}
      <section aria-labelledby="srs-handoff-heading">
        <Card>
          <CardHeader>
            <CardTitle id="srs-handoff-heading" className="text-lg">
              Cập nhật tiến trình ôn tập (SRS)
            </CardTitle>
            <CardDescription>
              Kết quả bài kiểm tra được chuyển giao nguyên tử sang hệ thống ôn tập Spaced Repetition một lần duy nhất từ máy chủ khi nộp bài.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.reviewHandoffs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Không có từ vựng nào cần cập nhật lịch ôn tập trong bài này.
              </p>
            ) : (
              <div className="divide-y divide-border border rounded-md overflow-hidden">
                {result.reviewHandoffs.map((handoff, idx) => (
                  <div
                    key={idx}
                    className="p-3 flex items-center justify-between text-sm bg-background flex-wrap gap-2"
                  >
                    <div>
                      <span className="font-medium text-foreground">
                        Từ vựng ID: <code className="text-xs bg-muted px-1 py-0.5 rounded">{handoff.wordFormId}</code>
                      </span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        Đánh giá: {ratingLabel(handoff.rating)}
                      </span>
                    </div>
                    <div>
                      {handoff.status === 'APPLIED' ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                          Đã cập nhật lịch ôn
                        </span>
                      ) : (
                        <span
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground"
                          title="Thẻ chưa kích hoạt trong hệ thống ôn tập"
                        >
                          Bỏ qua (Chưa kích hoạt)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
};
