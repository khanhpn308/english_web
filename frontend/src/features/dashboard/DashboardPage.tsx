import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ApiError, apiClient } from '@/shared/api/client';
import { RecoveryPanel } from '@/shared/errors/RecoveryPanel';
import { RotateCw, RefreshCcw, BookOpen, Flame, Award, CheckCircle } from 'lucide-react';

export type Rating = 'AGAIN' | 'HARD' | 'GOOD' | 'EASY';

export interface DashboardStreak {
  currentDays: number | null;
  asOf: string;
}

export interface FlashcardSelfRating {
  count: number;
  averageBucket: Rating | null;
}

export interface DashboardObjectiveScore {
  correct: number;
  total: number;
  attempted: number;
  accuracy: number | null;
}

export interface DashboardObjectiveAccuracy {
  mcq: DashboardObjectiveScore;
  cloze: DashboardObjectiveScore;
}

export interface DashboardWritingSelfScore {
  scored: number;
  average: number | null;
}

export interface DashboardSummary {
  dueCards: number;
  streak: DashboardStreak;
  flashcardSelfRating: FlashcardSelfRating;
  objectiveAccuracy: DashboardObjectiveAccuracy;
  writingSelfScore: DashboardWritingSelfScore;
}

export interface DashboardPageProps {
  onNavigate?: (path: string) => void;
}

function isObject(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

function isIntegerGteZero(val: unknown): val is number {
  return typeof val === 'number' && Number.isInteger(val) && val >= 0;
}

function isValidObjectiveScore(score: unknown): score is DashboardObjectiveScore {
  if (!isObject(score)) return false;
  return (
    isIntegerGteZero(score.correct) &&
    isIntegerGteZero(score.total) &&
    isIntegerGteZero(score.attempted) &&
    (score.accuracy === null || (typeof score.accuracy === 'number' && score.accuracy >= 0 && score.accuracy <= 1))
  );
}

function isValidDashboardSummary(data: unknown): data is DashboardSummary {
  if (!isObject(data)) return false;
  if (!isIntegerGteZero(data.dueCards)) return false;

  if (!isObject(data.streak)) return false;
  const streak = data.streak;
  if (streak.currentDays !== null && !isIntegerGteZero(streak.currentDays)) return false;
  if (typeof streak.asOf !== 'string') return false;

  if (!isObject(data.flashcardSelfRating)) return false;
  const flashcard = data.flashcardSelfRating;
  if (!isIntegerGteZero(flashcard.count)) return false;
  if (
    flashcard.averageBucket !== null &&
    !['AGAIN', 'HARD', 'GOOD', 'EASY'].includes(flashcard.averageBucket as string)
  ) {
    return false;
  }

  if (!isObject(data.objectiveAccuracy)) return false;
  const obj = data.objectiveAccuracy;
  if (!isValidObjectiveScore(obj.mcq) || !isValidObjectiveScore(obj.cloze)) return false;

  if (!isObject(data.writingSelfScore)) return false;
  const writing = data.writingSelfScore;
  if (!isIntegerGteZero(writing.scored)) return false;
  if (writing.average !== null && (typeof writing.average !== 'number' || writing.average < 0 || writing.average > 4)) {
    return false;
  }

  return true;
}

function ratingLabel(rating: Rating): string {
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

function formatAsOfDate(dateStr: string): string {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return dateStr;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown | null>(null);

  const requestSequence = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchDashboard = useCallback(async () => {
    const currentSeq = ++requestSequence.current;
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const result = await apiClient<DashboardSummary>('/api/v1/dashboard', {
        cache: 'no-store',
        signal: controller.signal,
      });

      if (currentSeq !== requestSequence.current) return;

      if (!isValidDashboardSummary(result)) {
        throw new Error('Dữ liệu tổng quan từ máy chủ không đúng định dạng.');
      }

      setData(result);
    } catch (err) {
      if (currentSeq !== requestSequence.current) return;
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError(err);
    } finally {
      if (currentSeq === requestSequence.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchDashboard();

    const handleInvalidation = () => {
      void fetchDashboard();
    };

    const handleFocus = () => {
      void fetchDashboard();
    };

    window.addEventListener('vocabulary:invalidate', handleInvalidation);
    window.addEventListener('focus', handleFocus);

    return () => {
      requestSequence.current += 1;
      abortControllerRef.current?.abort();
      window.removeEventListener('vocabulary:invalidate', handleInvalidation);
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchDashboard]);

  const handleNavigate = (path: string) => {
    if (onNavigate) {
      onNavigate(path);
    } else if (typeof window !== 'undefined') {
      window.location.assign(path);
    }
  };

  const isSyncing = error instanceof ApiError && error.code === 'STORAGE_BUSY';

  const isEntirelyEmpty =
    data !== null &&
    data.dueCards === 0 &&
    data.flashcardSelfRating.count === 0 &&
    data.objectiveAccuracy.mcq.attempted === 0 &&
    data.objectiveAccuracy.cloze.attempted === 0 &&
    data.writingSelfScore.scored === 0;

  return (
    <section aria-label="Bảng tổng quan học tập" className="space-y-6 min-w-0 break-words">
      {/* Action / Refresh bar */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <p className="text-sm text-muted-foreground m-0">
          Theo dõi số thẻ đến hạn ôn tập, chuỗi học tập liên tục và kết quả học tập độc lập.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void fetchDashboard()}
          disabled={loading}
          aria-label="Làm mới dữ liệu tổng quan"
          className="whitespace-nowrap"
        >
          <RotateCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} aria-hidden="true" />
          Làm mới
        </Button>
      </div>

      {/* Syncing State (STORAGE_BUSY) */}
      {isSyncing && (
        <Card className="border-amber-500/50 bg-amber-500/10" role="status" aria-live="polite">
          <CardHeader>
            <CardTitle className="text-amber-800 dark:text-amber-300 flex items-center gap-2 text-lg">
              <RefreshCcw className="w-5 h-5 animate-spin" aria-hidden="true" />
              Hệ thống đang đồng bộ dữ liệu (SYNCING)
            </CardTitle>
            <CardDescription className="text-foreground text-sm">
              Dữ liệu từ vựng đang được đồng bộ hoặc cơ sở dữ liệu đang bận. Dữ liệu tổng quan chưa sẵn sàng để hiển thị.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button variant="outline" onClick={() => void fetchDashboard()}>
              Thử lại ngay
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Error State */}
      {error && !isSyncing && (
        <RecoveryPanel
          error={error}
          onRetry={() => void fetchDashboard()}
          onReload={() => void fetchDashboard()}
          className="min-w-0"
        />
      )}

      {/* Loading Skeletons */}
      {loading && !data && (
        <div role="status" aria-live="polite" className="space-y-6">
          <p className="sr-only">Đang tải dữ liệu tổng quan...</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="h-44 bg-muted/30 animate-pulse">
              <CardHeader>
                <div className="h-5 w-40 bg-muted rounded" />
                <div className="h-4 w-60 bg-muted rounded mt-2" />
              </CardHeader>
              <CardContent>
                <div className="h-10 w-28 bg-muted rounded" />
              </CardContent>
            </Card>
            <Card className="h-44 bg-muted/30 animate-pulse">
              <CardHeader>
                <div className="h-5 w-40 bg-muted rounded" />
                <div className="h-4 w-60 bg-muted rounded mt-2" />
              </CardHeader>
              <CardContent>
                <div className="h-10 w-28 bg-muted rounded" />
              </CardContent>
            </Card>
          </div>
          <div className="space-y-4">
            <div className="h-6 w-48 bg-muted rounded" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="h-48 bg-muted/30 animate-pulse" />
              <Card className="h-48 bg-muted/30 animate-pulse" />
              <Card className="h-48 bg-muted/30 animate-pulse" />
              <Card className="h-48 bg-muted/30 animate-pulse" />
            </div>
          </div>
        </div>
      )}

      {/* Main Data Presentation */}
      {data && (
        <>
          {/* Top Row: Due Cards & Streak */}
          <section aria-labelledby="summary-metrics-heading" className="space-y-4">
            <h2 id="summary-metrics-heading" className="sr-only">
              Chỉ số tiến độ chính
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Due Cards Panel */}
              <Card aria-labelledby="due-cards-title">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle id="due-cards-title" className="text-lg font-semibold flex items-center gap-2">
                      <BookOpen className="w-5 h-5 text-primary" aria-hidden="true" />
                      Thẻ đến hạn ôn tập
                    </CardTitle>
                    <span
                      className={cn(
                        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                        data.dueCards > 0
                          ? 'bg-primary/10 text-primary'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {data.dueCards > 0 ? 'Có thẻ đến hạn' : 'Đã hoàn thành'}
                    </span>
                  </div>
                  <CardDescription>
                    Số thẻ từ vựng cần ôn tập hôm nay theo lịch lặp lại ngắt quãng (SRS)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-foreground">
                      {data.dueCards}
                    </span>
                    <span className="text-base text-muted-foreground font-medium">thẻ</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    {data.dueCards > 0
                      ? `Có ${data.dueCards} thẻ từ vựng đến hạn cần ôn tập.`
                      : 'Không có thẻ nào đến hạn hôm nay. Bạn đã hoàn tất các thẻ cần ôn!'}
                  </p>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button
                    onClick={() => handleNavigate('/review')}
                    variant={data.dueCards > 0 ? 'default' : 'outline'}
                    size="sm"
                    className="w-full sm:w-auto"
                  >
                    {data.dueCards > 0 ? 'Ôn tập ngay' : 'Xem hàng đợi ôn tập'}
                  </Button>
                </CardFooter>
              </Card>

              {/* Current Streak Panel */}
              <Card aria-labelledby="streak-title">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle id="streak-title" className="text-lg font-semibold flex items-center gap-2">
                      <Flame
                        className={cn(
                          'w-5 h-5',
                          data.streak.currentDays !== null && data.streak.currentDays > 0
                            ? 'text-amber-500'
                            : 'text-muted-foreground'
                        )}
                        aria-hidden="true"
                      />
                      Chuỗi học tập (Streak)
                    </CardTitle>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
                      {data.streak.asOf ? `Ngày ${formatAsOfDate(data.streak.asOf)}` : 'Asia/Bangkok'}
                    </span>
                  </div>
                  <CardDescription>
                    {data.streak.asOf
                      ? `Đánh giá theo ngày ${formatAsOfDate(data.streak.asOf)} (giờ Bangkok)`
                      : 'Số ngày hoàn thành mục tiêu học tập liên tiếp'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {data.streak.currentDays === null ? (
                    <div>
                      <div className="text-3xl font-bold text-muted-foreground">
                        Chưa xác định
                      </div>
                      <p className="text-sm text-muted-foreground mt-2">
                        Chưa đủ dữ liệu lịch sử đã lưu để tính chuỗi liên tục (không phải 0 ngày).
                      </p>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-baseline gap-2">
                        <span
                          className={cn(
                            'text-3xl font-bold',
                            data.streak.currentDays > 0
                              ? 'text-emerald-700 dark:text-emerald-400'
                              : 'text-foreground'
                          )}
                        >
                          {data.streak.currentDays}
                        </span>
                        <span className="text-base text-muted-foreground font-medium">ngày liên tiếp</span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-2">
                        {data.streak.currentDays > 0
                          ? `Đã duy trì học tập liên tục trong ${data.streak.currentDays} ngày.`
                          : 'Chưa có chuỗi ngày hoàn thành liên tiếp gần đây.'}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Bottom Section: Three Separated Learning Result Groups */}
          <section aria-labelledby="learning-results-title" className="space-y-4">
            <div className="space-y-1">
              <h2 id="learning-results-title" className="text-xl font-bold text-foreground">
                Kết quả học tập theo từng hình thức
              </h2>
              <p className="text-sm text-muted-foreground">
                Các nhóm kết quả học tập được theo dõi tách biệt, không gộp chung thành một điểm tổng.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Group 1: Flashcard Self Rating */}
              <Card aria-labelledby="flashcard-results-title">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle id="flashcard-results-title" className="text-base font-semibold flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-primary" aria-hidden="true" />
                      Tự đánh giá Flashcard
                    </CardTitle>
                    <span className="text-xs text-muted-foreground font-medium">
                      {data.flashcardSelfRating.count} lượt đánh giá
                    </span>
                  </div>
                  <CardDescription>
                    Đánh giá mức độ nhớ từ vựng khi lật thẻ flashcard
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                      Mức nhớ trung bình
                    </span>
                    {data.flashcardSelfRating.averageBucket === null || data.flashcardSelfRating.count === 0 ? (
                      <div>
                        <span className="text-2xl font-bold text-muted-foreground">Chưa có đánh giá</span>
                        <p className="text-xs text-muted-foreground mt-1">
                          Chưa có lượt ôn flashcard nào trong khoảng thời gian này.
                        </p>
                      </div>
                    ) : (
                      <div>
                        <span className="text-2xl font-bold text-primary">
                          {ratingLabel(data.flashcardSelfRating.averageBucket)}
                        </span>
                        <p className="text-xs text-muted-foreground mt-1">
                          Làm tròn theo quy tắc SRS ordinal mean.
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <span>Tổng số lượt đã đánh giá:</span>
                    <span className="font-semibold text-foreground">
                      {data.flashcardSelfRating.count} lượt
                    </span>
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleNavigate('/review')}
                    className="w-full sm:w-auto"
                  >
                    Ôn tập flashcard
                  </Button>
                </CardFooter>
              </Card>

              {/* Group 2: Trắc nghiệm (MCQ) Accuracy */}
              <Card aria-labelledby="mcq-results-title">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle id="mcq-results-title" className="text-base font-semibold flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-primary" aria-hidden="true" />
                      Trắc nghiệm (MCQ)
                    </CardTitle>
                    <span className="text-xs text-muted-foreground font-medium">
                      {data.objectiveAccuracy.mcq.attempted} / {data.objectiveAccuracy.mcq.total} câu
                    </span>
                  </div>
                  <CardDescription>
                    Độ chính xác các câu hỏi trắc nghiệm khách quan đã làm
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                      Độ chính xác
                    </span>
                    {data.objectiveAccuracy.mcq.accuracy === null || data.objectiveAccuracy.mcq.attempted === 0 ? (
                      <div>
                        <span className="text-2xl font-bold text-muted-foreground">Chưa làm câu nào</span>
                        <p className="text-xs text-muted-foreground mt-1">
                          Chưa có câu trắc nghiệm nào được làm (không tính là 0%).
                        </p>
                      </div>
                    ) : (
                      <div>
                        <span className="text-2xl font-bold text-primary">
                          {Math.round(data.objectiveAccuracy.mcq.accuracy * 100)}%
                        </span>
                        <div
                          className="w-full bg-secondary rounded-full h-2 mt-2 overflow-hidden"
                          role="progressbar"
                          aria-valuenow={Math.round(data.objectiveAccuracy.mcq.accuracy * 100)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label="Độ chính xác trắc nghiệm MCQ"
                        >
                          <div
                            className="bg-primary h-2 rounded-full transition-all duration-300"
                            style={{ width: `${Math.round(data.objectiveAccuracy.mcq.accuracy * 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <span>Số câu đúng / Đã làm:</span>
                    <span className="font-semibold text-foreground">
                      Đúng {data.objectiveAccuracy.mcq.correct} / {data.objectiveAccuracy.mcq.attempted} câu (Tổng: {data.objectiveAccuracy.mcq.total})
                    </span>
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleNavigate('/quiz/new')}
                    className="w-full sm:w-auto"
                  >
                    Tạo bài kiểm tra
                  </Button>
                </CardFooter>
              </Card>

              {/* Group 3: Điền từ (CLOZE) Accuracy */}
              <Card aria-labelledby="cloze-results-title">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle id="cloze-results-title" className="text-base font-semibold flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-primary" aria-hidden="true" />
                      Điền từ (CLOZE)
                    </CardTitle>
                    <span className="text-xs text-muted-foreground font-medium">
                      {data.objectiveAccuracy.cloze.attempted} / {data.objectiveAccuracy.cloze.total} câu
                    </span>
                  </div>
                  <CardDescription>
                    Độ chính xác các câu hỏi điền từ vào chỗ trống đã làm
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                      Độ chính xác
                    </span>
                    {data.objectiveAccuracy.cloze.accuracy === null || data.objectiveAccuracy.cloze.attempted === 0 ? (
                      <div>
                        <span className="text-2xl font-bold text-muted-foreground">Chưa làm câu nào</span>
                        <p className="text-xs text-muted-foreground mt-1">
                          Chưa có câu điền từ nào được làm (không tính là 0%).
                        </p>
                      </div>
                    ) : (
                      <div>
                        <span className="text-2xl font-bold text-primary">
                          {Math.round(data.objectiveAccuracy.cloze.accuracy * 100)}%
                        </span>
                        <div
                          className="w-full bg-secondary rounded-full h-2 mt-2 overflow-hidden"
                          role="progressbar"
                          aria-valuenow={Math.round(data.objectiveAccuracy.cloze.accuracy * 100)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label="Độ chính xác điền từ CLOZE"
                        >
                          <div
                            className="bg-primary h-2 rounded-full transition-all duration-300"
                            style={{ width: `${Math.round(data.objectiveAccuracy.cloze.accuracy * 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <span>Số câu đúng / Đã làm:</span>
                    <span className="font-semibold text-foreground">
                      Đúng {data.objectiveAccuracy.cloze.correct} / {data.objectiveAccuracy.cloze.attempted} câu (Tổng: {data.objectiveAccuracy.cloze.total})
                    </span>
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleNavigate('/quiz/new')}
                    className="w-full sm:w-auto"
                  >
                    Tạo bài kiểm tra
                  </Button>
                </CardFooter>
              </Card>

              {/* Group 4: Tự chấm Viết câu (WRITING Self-Score) */}
              <Card aria-labelledby="writing-results-title">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle id="writing-results-title" className="text-base font-semibold flex items-center gap-2">
                      <Award className="w-4 h-4 text-primary" aria-hidden="true" />
                      Tự chấm Viết câu
                    </CardTitle>
                    <span className="text-xs text-muted-foreground font-medium">
                      {data.writingSelfScore.scored} câu đã chấm
                    </span>
                  </div>
                  <CardDescription>
                    Điểm người học tự đánh giá theo thang rubric 0–4
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                      Điểm trung bình (Thang 0–4)
                    </span>
                    {data.writingSelfScore.average === null || data.writingSelfScore.scored === 0 ? (
                      <div>
                        <span className="text-2xl font-bold text-muted-foreground">Chưa có bài tự chấm</span>
                        <p className="text-xs text-muted-foreground mt-1">
                          Chưa có câu viết nào được tự chấm điểm theo rubric.
                        </p>
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-2xl font-bold text-primary">
                            {data.writingSelfScore.average.toFixed(1)}
                          </span>
                          <span className="text-sm text-muted-foreground font-medium">/ 4</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Điểm trung bình tự chấm cho {data.writingSelfScore.scored} câu đã làm.
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <span>Số câu viết đã tự chấm điểm:</span>
                    <span className="font-semibold text-foreground">
                      {data.writingSelfScore.scored} câu
                    </span>
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleNavigate('/quiz/new')}
                    className="w-full sm:w-auto"
                  >
                    Luyện viết câu
                  </Button>
                </CardFooter>
              </Card>
            </div>
          </section>

          {/* Empty History Guidance Card (shown when all learning activity is 0/empty) */}
          {isEntirelyEmpty && (
            <Card className="bg-muted/30 border-dashed" role="region" aria-label="Hướng dẫn bắt đầu">
              <CardHeader>
                <CardTitle className="text-base font-semibold">Chưa có lịch sử học tập</CardTitle>
                <CardDescription>
                  Hệ thống chưa ghi nhận lượt học tập nào trong kho dữ liệu. Bạn có thể bắt đầu bằng việc tra cứu từ mới, ôn tập flashcard hoặc làm bài kiểm tra.
                </CardDescription>
              </CardHeader>
              <CardFooter className="flex flex-wrap gap-3">
                <Button onClick={() => handleNavigate('/lookup')} size="sm">
                  Tra cứu từ mới
                </Button>
                <Button onClick={() => handleNavigate('/review')} variant="outline" size="sm">
                  Ôn tập flashcard
                </Button>
                <Button onClick={() => handleNavigate('/quiz/new')} variant="outline" size="sm">
                  Tạo bài kiểm tra
                </Button>
              </CardFooter>
            </Card>
          )}
        </>
      )}
    </section>
  );
};
