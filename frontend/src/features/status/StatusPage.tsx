import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { apiClient } from '@/shared/api/client';
import { RecoveryPanel } from '@/shared/errors/RecoveryPanel';
import { AiConsentPanel } from '@/features/consent/AiConsentPanel';
import type { components } from '@/shared/api/generated';
import { RotateCw, RefreshCcw, AlertCircle, CheckCircle } from 'lucide-react';

export type StatusSummary = components['schemas']['StatusSummary'];
export type BridgeStatus = components['schemas']['BridgeStatus'];
export type StorageStatus = components['schemas']['StorageStatus'];
export type OfflineCapabilities = components['schemas']['OfflineCapabilities'];
export type LocalMetricsSummary = components['schemas']['LocalMetricsSummary'];
export type SourceCounts = components['schemas']['SourceCounts'];

function isObject(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

export function isValidStatusSummary(data: unknown): data is StatusSummary {
  if (!isObject(data)) return false;
  if (typeof data.appVersion !== 'string') return false;
  if (!['NOT_READY', 'SYNCING', 'READY', 'DEGRADED', 'UNKNOWN'].includes(data.readiness as string)) return false;
  if (!['NOT_CHECKED', 'OK', 'NOT_READY'].includes(data.bridgeStatus as string)) return false;
  if (!['NOT_GRANTED', 'GRANTED', 'REVOKED', 'STALE', 'UNKNOWN'].includes(data.consentState as string)) return false;
  if (!['READY', 'NOT_READY', 'UNAVAILABLE', 'UNKNOWN'].includes(data.searchIndexStatus as string)) return false;
  if (typeof data.storageStatus !== 'string') return false;
  if (typeof data.requestId !== 'string') return false;
  if (!isObject(data.offlineCapabilities)) return false;
  if (!isObject(data.localMetrics)) return false;
  if (data.sourceCounts !== null && !isObject(data.sourceCounts)) return false;
  return true;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) {
    return 'Không xác định';
  }
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatUptime(seconds: number | null): string {
  if (seconds === null || typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) {
    return 'Không xác định';
  }
  const s = Math.floor(seconds);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const remainingSecs = s % 60;
  if (days > 0) return `${days} ngày ${hours} giờ ${minutes} phút`;
  if (hours > 0) return `${hours} giờ ${minutes} phút`;
  if (minutes > 0) return `${minutes} phút ${remainingSecs} giây`;
  return `${remainingSecs} giây`;
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return 'Chưa có thông tin / Không xác định';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return 'Không xác định';
    return d.toLocaleString('vi-VN', {
      timeZone: 'Asia/Bangkok',
      hour12: false,
    });
  } catch {
    return 'Không xác định';
  }
}

function formatDuration(ms: number | null): string {
  if (ms === null || typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) {
    return 'Không xác định';
  }
  return `${ms.toLocaleString('vi-VN')} ms`;
}

function getReadinessInfo(readiness: string): { label: string; description: string; className: string } {
  switch (readiness) {
    case 'READY':
      return {
        label: 'Sẵn sàng (READY)',
        description: 'Hệ thống sẵn sàng: lưu trữ cục bộ, nguồn từ vựng và dịch vụ hoạt động bình thường.',
        className: 'text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      };
    case 'SYNCING':
      return {
        label: 'Đang đồng bộ (SYNCING)',
        description: 'Hệ thống đang đồng bộ hóa tệp nguồn Markdown vào cơ sở dữ liệu.',
        className: 'text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
      };
    case 'DEGRADED':
      return {
        label: 'Hoạt động suy giảm (DEGRADED)',
        description: 'Một số thành phần gặp sự cố (như kết nối AI bridge hoặc tệp nguồn); học tập cục bộ vẫn khả dụng.',
        className: 'text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
      };
    case 'NOT_READY':
      return {
        label: 'Chưa sẵn sàng (NOT_READY)',
        description: 'Hệ thống chưa hoàn tất quá trình khởi tạo hoặc cơ sở dữ liệu chưa sẵn sàng.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    default:
      return {
        label: `Không xác định (${readiness || 'UNKNOWN'})`,
        description: 'Chưa nhận được cờ trạng thái sẵn sàng từ máy chủ.',
        className: 'text-muted-foreground bg-muted border-border',
      };
  }
}

function getBridgeStatusInfo(status: string): { label: string; description: string; className: string } {
  switch (status) {
    case 'OK':
      return {
        label: 'Hoạt động bình thường (OK)',
        description: 'Đã quan sát thấy kết nối thành công với AI bridge gần đây.',
        className: 'text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      };
    case 'NOT_READY':
      return {
        label: 'Không khả dụng / Chưa sẵn sàng (NOT_READY)',
        description: 'AI bridge đang tắt hoặc không kết nối được. Các thao tác AI tạm thời bị chặn; học tập cục bộ vẫn hoạt động bình thường.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    case 'NOT_CHECKED':
      return {
        label: 'Chưa kiểm tra gần đây (NOT_CHECKED)',
        description: 'Chưa thực hiện cuộc gọi AI gần đây để ghi nhận trạng thái kết nối.',
        className: 'text-muted-foreground bg-muted border-border',
      };
    default:
      return {
        label: `Không xác định (${status})`,
        description: 'Không có dữ liệu trạng thái kết nối bridge.',
        className: 'text-muted-foreground bg-muted border-border',
      };
  }
}

function getStorageStatusInfo(status: string): { label: string; description: string; className: string } {
  switch (status) {
    case 'OK':
      return {
        label: 'Bình thường (OK)',
        description: 'Cơ sở dữ liệu SQLite đã sẵn sàng và lược đồ khớp với phiên bản hệ thống.',
        className: 'text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      };
    case 'BUSY':
      return {
        label: 'Đang bận (BUSY)',
        description: 'Cơ sở dữ liệu SQLite đang xử lý ghi khác, các yêu cầu có thể bị hoãn ngắn.',
        className: 'text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
      };
    case 'READ_ONLY':
      return {
        label: 'Chỉ đọc (READ_ONLY)',
        description: 'Cơ sở dữ liệu đang ở chế độ chỉ đọc, không thể ghi dữ liệu mới.',
        className: 'text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
      };
    case 'INTEGRITY_FAILED':
      return {
        label: 'Lỗi toàn vẹn (INTEGRITY_FAILED)',
        description: 'Kiểm tra PRAGMA integrity_check phát hiện lỗi dữ liệu. Vui lòng kiểm tra sổ tay vận hành.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    case 'SCHEMA_MISMATCH':
      return {
        label: 'Lỗi lược đồ (SCHEMA_MISMATCH)',
        description: 'Phiên bản di chuyển cơ sở dữ liệu không khớp với phiên bản mã nguồn.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    case 'NOT_READY':
      return {
        label: 'Chưa sẵn sàng (NOT_READY)',
        description: 'Lưu trữ SQLite chưa hoàn tất khởi tạo ban đầu.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    case 'UNAVAILABLE':
      return {
        label: 'Không khả dụng (UNAVAILABLE)',
        description: 'Không thể truy cập tệp cơ sở dữ liệu SQLite.',
        className: 'text-rose-700 dark:text-rose-400 bg-rose-500/10 border-rose-500/30',
      };
    default:
      return {
        label: `Không xác định (${status})`,
        description: 'Chưa có thông tin trạng thái lưu trữ.',
        className: 'text-muted-foreground bg-muted border-border',
      };
  }
}

function getSearchIndexStatusLabel(status: string): string {
  switch (status) {
    case 'READY': return 'Sẵn sàng (READY)';
    case 'NOT_READY': return 'Chưa sẵn sàng (NOT_READY)';
    case 'UNAVAILABLE': return 'Không khả dụng (UNAVAILABLE)';
    default: return `Không xác định (${status})`;
  }
}

function getConsentStateLabel(state: string): string {
  switch (state) {
    case 'GRANTED': return 'Đã cấp quyền (GRANTED)';
    case 'NOT_GRANTED': return 'Chưa cấp quyền (NOT_GRANTED)';
    case 'REVOKED': return 'Đã rút quyền (REVOKED)';
    case 'STALE': return 'Chính sách đã cập nhật (STALE)';
    default: return `Không xác định (${state})`;
  }
}

function formatCapabilityStatus(val: boolean | null): { text: string; badgeClass: string } {
  if (val === true) {
    return {
      text: 'Khả dụng ngoại tuyến (Có)',
      badgeClass: 'text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    };
  }
  if (val === false) {
    return {
      text: 'Cần mạng / Không hỗ trợ (Không)',
      badgeClass: 'text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/30',
    };
  }
  return {
    text: 'Không xác định / Phụ thuộc trình duyệt',
    badgeClass: 'text-muted-foreground bg-muted border-border',
  };
}

export const StatusPage: React.FC = () => {
  const [data, setData] = useState<StatusSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown | null>(null);
  const [lastPolledAt, setLastPolledAt] = useState<Date | null>(null);

  const requestSequence = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchStatus = useCallback(async () => {
    const currentSeq = ++requestSequence.current;
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const result = await apiClient<StatusSummary>('/api/v1/status', {
        cache: 'no-store',
        signal: controller.signal,
      });

      if (currentSeq !== requestSequence.current) return;

      if (!isValidStatusSummary(result)) {
        throw new Error('Dữ liệu trạng thái từ máy chủ không đúng định dạng.');
      }

      setData(result);
      setLastPolledAt(new Date());
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
    let timerId: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      stopPolling();
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        // shortcut: 30-second fixed poll, upgrade to SSE/WebSocket if push events become available
        timerId = setInterval(() => {
          if (document.visibilityState === 'visible') {
            void fetchStatus();
          }
        }, 30000);
      }
    };

    const stopPolling = () => {
      if (timerId !== null) {
        clearInterval(timerId);
        timerId = null;
      }
    };

    // Initial fetch
    void fetchStatus();
    startPolling();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void fetchStatus();
        startPolling();
      } else {
        stopPolling();
      }
    };

    const handleFocus = () => {
      if (document.visibilityState === 'visible') {
        void fetchStatus();
        startPolling();
      }
    };

    const handleInvalidate = () => {
      void fetchStatus();
      startPolling();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('vocabulary:invalidate', handleInvalidate);

    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('vocabulary:invalidate', handleInvalidate);
      requestSequence.current += 1;
      abortControllerRef.current?.abort();
    };
  }, [fetchStatus]);

  const readinessInfo = data ? getReadinessInfo(data.readiness) : null;
  const bridgeInfo = data ? getBridgeStatusInfo(data.bridgeStatus) : null;
  const storageInfo = data ? getStorageStatusInfo(data.storageStatus) : null;

  const offlineCapabilitiesList = data ? [
    {
      name: 'Tìm kiếm từ vựng (Search)',
      key: 'search',
      status: data.offlineCapabilities.search,
      notes: 'Tìm kiếm nghĩa và dạng từ từ dữ liệu đã lưu trên máy',
    },
    {
      name: 'Ôn tập thẻ nhớ (Review)',
      key: 'review',
      status: data.offlineCapabilities.review,
      notes: 'Luyện tập flashcard theo thuật toán SRS cục bộ',
    },
    {
      name: 'Bảng tổng quan học tập (Dashboard)',
      key: 'dashboard',
      status: data.offlineCapabilities.dashboard,
      notes: 'Xem tiến độ học tập, chuỗi ngày học và số thẻ đến hạn',
    },
    {
      name: 'Làm bài kiểm tra đã tạo (Created Quiz)',
      key: 'createdQuiz',
      status: data.offlineCapabilities.createdQuiz,
      notes: 'Làm và chấm điểm các bài trắc nghiệm / điền từ đã tạo sẵn',
    },
    {
      name: 'Tra cứu trực tuyến mới (Lookup)',
      key: 'lookup',
      status: false,
      notes: 'Yêu cầu kết nối AI bridge để trích xuất và tra cứu từ mới',
    },
    {
      name: 'Tạo bài kiểm tra AI mới (New Quiz)',
      key: 'newQuiz',
      status: false,
      notes: 'Yêu cầu kết nối AI bridge để tạo câu hỏi mới từ bài báo',
    },
    {
      name: 'Phản hồi bài viết AI (Writing Feedback)',
      key: 'feedback',
      status: false,
      notes: 'Yêu cầu kết nối AI bridge để đánh giá câu trả lời viết',
    },
    {
      name: 'Phát âm giọng nói (Audio Pronunciation)',
      key: 'audio',
      status: data.offlineCapabilities.audio,
      notes: 'Sử dụng công nghệ SpeechSynthesis tích hợp sẵn trong trình duyệt',
    },
  ] : [];

  return (
    <section aria-label="Trạng thái hệ thống và vận hành" className="space-y-6 min-w-0 break-words">
      {/* Top action / refresh bar */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-sm text-muted-foreground m-0">
            Theo dõi tình trạng hoạt động, mức độ sẵn sàng ngoại tuyến, kết nối AI và lưu trữ cục bộ.
          </p>
          {lastPolledAt && (
            <p className="text-xs text-muted-foreground mt-1 m-0">
              Cập nhật gần nhất: {lastPolledAt.toLocaleTimeString('vi-VN', { hour12: false })} (thăm dò tự động mỗi 30 giây khi hiển thị)
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void fetchStatus()}
          disabled={loading}
          aria-label="Làm mới trạng thái hệ thống"
          className="whitespace-nowrap"
        >
          <RotateCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} aria-hidden="true" />
          Làm mới
        </Button>
      </div>

      {/* Loading state indicator when no data yet */}
      {loading && !data && (
        <Card role="status" aria-busy="true" aria-live="polite" className="p-6 text-center">
          <div className="flex items-center justify-center gap-3">
            <RefreshCcw className="w-5 h-5 animate-spin text-primary" aria-hidden="true" />
            <p className="text-base font-medium m-0 text-foreground">
              Đang kiểm tra và tải trạng thái hệ thống...
            </p>
          </div>
        </Card>
      )}

      {/* Error State when no data */}
      {error && !data && (
        <RecoveryPanel
          error={error}
          onRetry={() => void fetchStatus()}
          onReload={() => void fetchStatus()}
        />
      )}

      {/* Background refresh error banner when data already loaded */}
      {error && data && (
        <div role="alert" aria-live="polite">
          <RecoveryPanel
            error={error}
            onRetry={() => void fetchStatus()}
            onReload={() => void fetchStatus()}
          />
        </div>
      )}

      {/* Successful Status Display */}
      {data && readinessInfo && bridgeInfo && storageInfo && (
        <div className="space-y-6">
          {/* Card 1: System Readiness & Overview */}
          <Card role="region" aria-labelledby="status-readiness-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-readiness-heading" className="text-xl font-semibold m-0">
                  Mức độ sẵn sàng hệ thống
                </h2>
              </CardTitle>
              <CardDescription>
                Tổng quan mức độ sẵn sàng của ứng dụng và thông tin phiên bản
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className={cn('p-4 rounded-lg border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3', readinessInfo.className)}>
                <div>
                  <div className="flex items-center gap-2">
                    {data.readiness === 'READY' ? (
                      <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                    ) : (
                      <AlertCircle className="w-5 h-5" aria-hidden="true" />
                    )}
                    <span className="font-bold text-base">{readinessInfo.label}</span>
                  </div>
                  <p className="mt-1 text-xs text-foreground/80 m-0">{readinessInfo.description}</p>
                </div>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 m-0">
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Phiên bản ứng dụng</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">{data.appVersion}</dd>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Thời gian hoạt động</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">{formatUptime(data.uptimeSeconds)}</dd>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Mã định danh yêu cầu</dt>
                  <dd className="mt-1 text-sm font-mono text-foreground break-all m-0">{data.requestId}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Card 2: Storage & SQLite Database */}
          <Card role="region" aria-labelledby="status-storage-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-storage-heading" className="text-xl font-semibold m-0">
                  Trạng thái lưu trữ & Cơ sở dữ liệu
                </h2>
              </CardTitle>
              <CardDescription>
                Tình trạng cơ sở dữ liệu SQLite cục bộ, tính toàn vẹn và mức độ bận
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 m-0">
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Trạng thái lưu trữ (Storage Status)</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">{storageInfo.label}</dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">{storageInfo.description}</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Phiên bản lược đồ (Schema Revision)</dt>
                  <dd className="mt-1 text-sm font-mono font-medium text-foreground m-0">
                    {data.schemaRevision || 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Mã định danh phiên bản di chuyển Alembic hiện tại</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Kiểm tra toàn vẹn gần nhất</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {formatDateTime(data.lastIntegrityCheckAt)}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Kiểm tra PRAGMA foreign_key_check và toàn vẹn lúc khởi động</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Kích thước tệp cơ sở dữ liệu</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {formatBytes(data.sqliteFileSizeBytes)}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Kích thước tệp SQLite chính (không hiển thị đường dẫn tệp)</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border sm:col-span-2">
                  <dt className="text-xs font-semibold text-muted-foreground">Số lần khóa bận (SQLite Busy Count)</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {data.sqliteBusyCount !== null ? `${data.sqliteBusyCount} lần` : 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Số lần ghi nhận lỗi SQLITE_BUSY / SQLITE_LOCKED từ lúc khởi động tiến trình</p>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Card 3: Source Markdown & Sync */}
          <Card role="region" aria-labelledby="status-source-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-source-heading" className="text-xl font-semibold m-0">
                  Nguồn từ vựng Markdown & Đồng bộ
                </h2>
              </CardTitle>
              <CardDescription>
                Số lượng tệp ghi chú Markdown, trạng thái đồng bộ và chỉ mục tìm kiếm
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 m-0">
                <div className="p-3 rounded-md bg-muted/40 border sm:col-span-2">
                  <dt className="text-xs font-semibold text-muted-foreground">Trạng thái tệp nguồn Markdown</dt>
                  <dd className="mt-2 m-0">
                    {data.sourceCounts ? (
                      <div className="flex flex-wrap gap-4 text-sm">
                        <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700 dark:text-emerald-400">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" aria-hidden="true" />
                          Hợp lệ (VALID): <strong>{data.sourceCounts.VALID}</strong>
                        </span>
                        <span className="inline-flex items-center gap-1.5 font-medium text-amber-700 dark:text-amber-400">
                          <span className="w-2 h-2 rounded-full bg-amber-500" aria-hidden="true" />
                          Không hợp lệ (INVALID): <strong>{data.sourceCounts.INVALID}</strong>
                        </span>
                        <span className="inline-flex items-center gap-1.5 font-medium text-rose-700 dark:text-rose-400">
                          <span className="w-2 h-2 rounded-full bg-rose-500" aria-hidden="true" />
                          Thiếu (MISSING): <strong>{data.sourceCounts.MISSING}</strong>
                        </span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-sm">Không xác định hoặc cơ sở dữ liệu chưa sẵn sàng</span>
                    )}
                  </dd>
                  <p className="mt-2 text-xs text-muted-foreground m-0">
                    Các tệp không hợp lệ sẽ tự động bị loại khỏi hàng đợi học tập để bảo vệ dữ liệu.
                  </p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Lần đồng bộ thành công gần nhất</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {formatDateTime(data.lastSyncAt)}
                  </dd>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Thời gian đồng bộ</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {formatDuration(data.lastSyncDurationMs)}
                  </dd>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border sm:col-span-2">
                  <dt className="text-xs font-semibold text-muted-foreground">Chỉ mục tìm kiếm (Search Index)</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {getSearchIndexStatusLabel(data.searchIndexStatus)}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Trạng thái chỉ mục tìm kiếm n-gram cho từ vựng và nghĩa tiếng Việt</p>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Card 4: AI Bridge & Model Configuration */}
          <Card role="region" aria-labelledby="status-bridge-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-bridge-heading" className="text-xl font-semibold m-0">
                  Kết nối AI Bridge & Mô hình
                </h2>
              </CardTitle>
              <CardDescription>
                Tình trạng cầu nối Antigravity Tools và chính sách mô hình AI
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 m-0">
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Trạng thái AI Bridge (Bridge Status)</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">{bridgeInfo.label}</dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">{bridgeInfo.description}</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Họ mô hình AI đã cấu hình</dt>
                  <dd className="mt-1 text-sm font-mono font-medium text-foreground m-0">
                    {data.selectedModelFamily || 'Chưa cấu hình / Không khả dụng'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Chỉ hiển thị họ mô hình được phê duyệt theo chính sách v1 (gemini-3.8-flash-high)</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Phiên bản chính sách AI</dt>
                  <dd className="mt-1 text-sm font-mono font-medium text-foreground m-0">
                    {data.policyVersion || 'Chưa xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Phiên bản chính sách công bố dữ liệu hiện tại</p>
                </div>
                <div className="p-3 rounded-md bg-muted/40 border">
                  <dt className="text-xs font-semibold text-muted-foreground">Trạng thái quyền gửi dữ liệu AI</dt>
                  <dd className="mt-1 text-sm font-medium text-foreground m-0">
                    {getConsentStateLabel(data.consentState)}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Xem chi tiết và tùy chỉnh tại phần Quản lý quyền AI bên dưới</p>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Card 5: Offline Capabilities Matrix */}
          <Card role="region" aria-labelledby="status-offline-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-offline-heading" className="text-xl font-semibold m-0">
                  Khả năng hoạt động ngoại tuyến (Offline)
                </h2>
              </CardTitle>
              <CardDescription>
                Ma trận tính năng phân biệt giữa khả năng hoạt động độc lập không cần mạng và tính năng yêu cầu AI
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse" role="table" aria-label="Bảng khả năng hoạt động ngoại tuyến">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th scope="col" className="p-3 font-semibold text-foreground">Tính năng</th>
                      <th scope="col" className="p-3 font-semibold text-foreground">Khả năng ngoại tuyến</th>
                      <th scope="col" className="p-3 font-semibold text-foreground">Mô tả hoạt động</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {offlineCapabilitiesList.map((item) => {
                      const formatted = formatCapabilityStatus(item.status);
                      return (
                        <tr key={item.key} className="hover:bg-muted/30">
                          <td className="p-3 font-medium text-foreground">{item.name}</td>
                          <td className="p-3">
                            <span className={cn('inline-block px-2 py-0.5 text-xs font-semibold rounded border', formatted.badgeClass)}>
                              {formatted.text}
                            </span>
                          </td>
                          <td className="p-3 text-muted-foreground">{item.notes}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Card 6: Local RED Metrics */}
          <Card role="region" aria-labelledby="status-metrics-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-metrics-heading" className="text-xl font-semibold m-0">
                  Chỉ số hiệu năng cục bộ (Local Metrics)
                </h2>
              </CardTitle>
              <CardDescription>
                Tỷ lệ lỗi và các phân vị thời gian phản hồi đo lường trên máy cục bộ trong 5 phút gần nhất
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 m-0">
                <div className="p-4 rounded-lg border bg-card">
                  <dt className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Tỷ lệ lỗi (5xx Error Rate)</dt>
                  <dd className="mt-2 text-2xl font-bold text-foreground m-0">
                    {data.localMetrics.requestErrorRate !== null
                      ? `${(data.localMetrics.requestErrorRate * 100).toFixed(2)}%`
                      : 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Ngưỡng cảnh báo: &gt; 1% trong 5 phút</p>
                </div>
                <div className="p-4 rounded-lg border bg-card">
                  <dt className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Độ trễ p50</dt>
                  <dd className="mt-2 text-2xl font-bold text-foreground m-0">
                    {data.localMetrics.p50Ms !== null ? `${data.localMetrics.p50Ms} ms` : 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Thời gian phản hồi trung vị</p>
                </div>
                <div className="p-4 rounded-lg border bg-card">
                  <dt className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Độ trễ p95</dt>
                  <dd className="mt-2 text-2xl font-bold text-foreground m-0">
                    {data.localMetrics.p95Ms !== null ? `${data.localMetrics.p95Ms} ms` : 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Phần trăm phân vị thứ 95</p>
                </div>
                <div className="p-4 rounded-lg border bg-card">
                  <dt className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Độ trễ p99</dt>
                  <dd className="mt-2 text-2xl font-bold text-foreground m-0">
                    {data.localMetrics.p99Ms !== null ? `${data.localMetrics.p99Ms} ms` : 'Không xác định'}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground m-0">Phần trăm phân vị thứ 99</p>
                </div>
              </dl>
              <p className="text-xs text-muted-foreground m-0">
                Thời điểm lấy mẫu gần nhất: {formatDateTime(data.localMetrics.sampledAt)}
              </p>
            </CardContent>
          </Card>

          {/* Card 7: Runbooks */}
          <Card role="region" aria-labelledby="status-runbooks-heading">
            <CardHeader>
              <CardTitle>
                <h2 id="status-runbooks-heading" className="text-xl font-semibold m-0">
                  Tài liệu vận hành & Hướng dẫn xử lý sự cố (Runbooks)
                </h2>
              </CardTitle>
              <CardDescription>
                Các tài liệu hướng dẫn khắc phục sự cố cục bộ khi gặp cảnh báo vận hành
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground list-disc pl-5 m-0">
                <li>
                  <strong className="text-foreground">Máy chủ API không phản hồi:</strong> Khởi động lại ứng dụng nếu 2 lần thăm dò liên tiếp thất bại. Không làm mất cơ sở dữ liệu SQLite. (<code className="font-mono text-xs">docs/runbooks/api-unavailable.md</code>)
                </li>
                <li>
                  <strong className="text-foreground">Tỷ lệ lỗi API &gt; 1%:</strong> Kiểm tra mã yêu cầu (requestId) trong nhật ký cục bộ. (<code className="font-mono text-xs">docs/runbooks/api-error-rate.md</code>)
                </li>
                <li>
                  <strong className="text-foreground">AI bridge không kết nối:</strong> Chỉ tạm dừng các chức năng cần AI; ôn tập và tra cứu cục bộ tiếp tục hoạt động. (<code className="font-mono text-xs">docs/runbooks/bridge-failure.md</code>)
                </li>
                <li>
                  <strong className="text-foreground">Lỗi toàn vẹn cơ sở dữ liệu:</strong> Ngừng các thao tác ghi và làm theo hướng dẫn khôi phục dữ liệu an toàn. (<code className="font-mono text-xs">docs/runbooks/storage-integrity.md</code>)
                </li>
                <li>
                  <strong className="text-foreground">Tệp nguồn Markdown không hợp lệ:</strong> Sửa định dạng tệp bị lỗi hoặc khôi phục từ bản sao lưu. (<code className="font-mono text-xs">docs/runbooks/source-sync.md</code>)
                </li>
                <li>
                  <strong className="text-foreground">Hiệu năng tìm kiếm từ vựng suy giảm:</strong> Kiểm tra chỉ mục n-gram và kích thước cơ sở dữ liệu. (<code className="font-mono text-xs">docs/runbooks/search-performance.md</code>)
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Render AI Consent Panel at #ai-consent */}
      <AiConsentPanel />
    </section>
  );
};
