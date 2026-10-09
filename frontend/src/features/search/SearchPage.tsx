import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ApiError, NetworkError, apiClient } from '@/shared/api/client';
import type { components, operations } from '@/shared/api/generated';
import { RecoveryPanel } from '@/shared/errors/RecoveryPanel';

type Page = components['schemas']['WordFormCollection'];
type Query = NonNullable<operations['list_word_forms_api_v1_word_forms_get']['parameters']['query']>;
export type Navigate = (path: string, replace?: boolean) => void;
const queryKeys = ['meaningVi', 'lemma', 'partOfSpeech', 'verificationStatus', 'noteDate', 'sourceStatus', 'pageSize', 'sortBy', 'sortOrder', 'cursor'] as const satisfies readonly (keyof Query)[];
export const verificationLabels = { VERIFIED: 'Đã xác minh', UNVERIFIED: 'Chưa xác minh', MISSING: 'Thiếu thông tin xác minh' } satisfies Record<Page['data'][number]['verificationSummary'], string>;
const controlClass = 'w-full min-w-0 rounded-md border border-input bg-background px-3 py-2 text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring';

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
export function isVerification(value: unknown): value is keyof typeof verificationLabels {
  return value === 'VERIFIED' || value === 'UNVERIFIED' || value === 'MISSING';
}
export function isWordForm(value: unknown): value is Omit<Page['data'][number], 'meaningViMatch' | 'noteDates'> {
  return isObject(value) && typeof value.id === 'string' && typeof value.lemma === 'string'
    && typeof value.partOfSpeech === 'string' && typeof value.updatedAt === 'string'
    && Number.isInteger(value.revision) && typeof value.revision === 'number' && value.revision >= 0
    && isVerification(value.verificationSummary);
}
function isCollection(value: unknown): value is Page {
  if (!isObject(value) || !Array.isArray(value.data) || !isObject(value.pagination) || !isObject(value.sort)) return false;
  const { pagination, sort } = value;
  return value.data.length <= 100 && value.data.every(form => isWordForm(form) && isObject(form)
    && typeof form.meaningViMatch === 'string' && Array.isArray(form.noteDates) && form.noteDates.every(date => typeof date === 'string'))
    && typeof pagination.hasMore === 'boolean' && (pagination.nextCursor === null || typeof pagination.nextCursor === 'string')
    && typeof pagination.pageSize === 'number' && Number.isInteger(pagination.pageSize) && pagination.pageSize >= 1 && pagination.pageSize <= 100
    && (sort.by === 'relevance' || sort.by === 'updatedAt' || sort.by === 'lemma') && (sort.direction === 'ASC' || sort.direction === 'DESC');
}

// Keyed state also hides an old page during the render before effect cleanup.
export function useLocalRead<T>(url: string | null, retry: number, validate: (value: unknown) => value is T) {
  const generation = useRef(0);
  const [state, setState] = useState<{ key: string | null; retry: number; data?: T; error?: unknown }>({ key: null, retry: 0 });
  // Discard prior data even when navigating A -> B -> A before B resolves.
  if (state.key !== url || state.retry !== retry) setState({ key: url, retry });
  useEffect(() => {
    const identity = ++generation.current;
    const controller = new AbortController();
    if (url !== null) {
      apiClient<unknown>(url, { signal: controller.signal }).then(data => {
        if (!validate(data)) throw new Error('Invalid local read response');
        if (generation.current === identity && !controller.signal.aborted) setState({ key: url, retry, data });
      }).catch((error: unknown) => {
        if (generation.current === identity && !controller.signal.aborted) setState({ key: url, retry, error });
      });
    }
    return () => { generation.current += 1; controller.abort(); };
  }, [url, retry, validate]);
  const current = state.key === url && state.retry === retry;
  return { data: current ? state.data : undefined, error: current ? state.error : undefined, loading: url !== null && (!current || (!state.data && !state.error)) };
}

// T010's fallback may render raw messages. Only fixed copy and bounded IDs cross it.
export function ReadRecovery({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const messages: Record<string, string> = {
    NOT_FOUND: 'Không tìm thấy dạng từ. Dạng từ có thể đã bị xóa.',
    SOURCE_MISSING: 'Nguồn không còn tồn tại. Kiểm tra nguồn rồi tải lại.',
    SOURCE_INVALID: 'Nguồn không hợp lệ. Kiểm tra nguồn rồi tải lại.',
    INVALID_QUERY: 'Truy vấn không hợp lệ. Kiểm tra bộ lọc hoặc xóa bộ lọc.',
    VALIDATION_ERROR: 'Truy vấn không hợp lệ. Kiểm tra bộ lọc hoặc xóa bộ lọc.',
  };
  const code = error instanceof ApiError && typeof error.code === 'string' ? error.code : 'INTERNAL_ERROR';
  const safe = error instanceof ApiError
    ? new ApiError(error.status, { code, message: Object.hasOwn(messages, code) ? messages[code] : 'Không đọc được dữ liệu. Kiểm tra trạng thái hệ thống rồi thử lại.', requestId: typeof error.requestId === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(error.requestId) ? error.requestId : '' })
    : error instanceof NetworkError ? new NetworkError('Không kết nối được API cục bộ.', 'GET', '')
      : new ApiError(500, { code: 'INTERNAL_ERROR', message: 'Không đọc được dữ liệu.', requestId: '' });
  const session = error instanceof ApiError && ['SESSION_REQUIRED', 'SESSION_INVALID'].includes(code);
  return <div className="space-y-3 min-w-0 break-words">
    <RecoveryPanel error={safe} onRetry={onRetry} onReload={onRetry} onRebootstrap={() => window.location.reload()} className="min-w-0 [&_p]:break-words [&_p]:min-w-0 [&_button]:whitespace-normal [&_button]:h-auto" />
    {session && <p>Mở lại ứng dụng bằng trình khởi chạy để cấp phiên cục bộ mới, rồi tải lại địa chỉ này. Truy vấn vẫn nằm trong địa chỉ trang.</p>}
    <Button variant="outline" asChild><a href="/status">Kiểm tra trạng thái hệ thống</a></Button>
  </div>;
}

export function LocalLink({ href, onNavigate, children }: { href: string; onNavigate: Navigate; children: ReactNode }) {
  function follow(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    event.preventDefault(); onNavigate(href);
  }
  return <a href={href} onClick={follow} className="text-primary underline break-words rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{children}</a>;
}

export function SearchPage({ path, onNavigate }: { path: string; onNavigate: Navigate }) {
  useEffect(() => { document.querySelector<HTMLHeadingElement>('#main-content h1')?.focus(); }, []);
  const params = new URLSearchParams(path.includes('?') ? path.slice(path.indexOf('?') + 1) : '');
  const query = new URLSearchParams();
  for (const key of queryKeys) for (const value of params.getAll(key)) if (value) query.append(key, value);
  const active = params.get('browse') === '1' || query.size > 0;
  const [retry, setRetry] = useState(0);
  const view = useLocalRead<Page>(active ? `/api/v1/word-forms${query.size ? `?${query}` : ''}` : null, retry, isCollection);
  const cursorExpired = view.error instanceof ApiError && view.error.code === 'CURSOR_EXPIRED' && params.has('cursor');
  const restartPath = new URLSearchParams(params);
  restartPath.delete('cursor'); restartPath.set('notice', 'cursorExpired'); restartPath.set('browse', '1');
  const restart = `/search?${restartPath}`;
  useEffect(() => { if (cursorExpired) onNavigate(restart, true); }, [cursorExpired, restart, onNavigate]);

  function change(key: keyof Query | 'browse', value: string) {
    const next = new URLSearchParams(params);
    next.delete('notice');
    if (key !== 'cursor') next.delete('cursor');
    if (value) next.set(key, value); else next.delete(key);
    next.set('browse', '1'); onNavigate(`/search?${next}`);
  }
  function field(key: 'meaningVi' | 'lemma' | 'noteDate', label: string, type = 'search') {
    return <div className="min-w-0 space-y-1"><label htmlFor={key} className="block font-medium">{label}</label>
      <input id={key} type={type} value={params.get(key) ?? ''} onChange={event => change(key, event.target.value)} className={controlClass} maxLength={type === 'search' ? 4096 : undefined} />
    </div>;
  }
  function select(key: keyof Query, label: string, values: readonly (readonly [string, string])[], fallback = '') {
    const value = params.get(key) ?? fallback;
    return <div className="min-w-0 space-y-1"><label htmlFor={key} className="block font-medium">{label}</label>
      <select id={key} className={controlClass} value={value} onChange={event => change(key, event.target.value)}>
        {!fallback && <option value="">Tất cả</option>}
        {value && !values.some(([id]) => id === value) && <option value={value}>Giá trị không hợp lệ</option>}
        {values.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </div>;
  }
  return <section aria-label="Tìm trong kho từ" className="space-y-4 min-w-0">
    <Card><CardContent className="pt-6">
      <form className="space-y-4" onSubmit={event => { event.preventDefault(); if (active) setRetry(value => value + 1); else change('browse', '1'); }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {field('meaningVi', 'Nghĩa tiếng Việt')}{field('lemma', 'Dạng từ / lemma')}
          {select('partOfSpeech', 'Loại từ', [['NOUN', 'Danh từ'], ['VERB', 'Động từ'], ['ADJECTIVE', 'Tính từ'], ['ADVERB', 'Trạng từ'], ['PRONOUN', 'Đại từ'], ['PREPOSITION', 'Giới từ'], ['CONJUNCTION', 'Liên từ'], ['INTERJECTION', 'Thán từ'], ['DETERMINER', 'Từ hạn định']])}
          {select('verificationStatus', 'Xác minh', Object.entries(verificationLabels))}
          {field('noteDate', 'Ngày ghi chú', 'date')}
          {select('sourceStatus', 'Trạng thái nguồn', [['VALID', 'Hợp lệ'], ['INVALID', 'Không hợp lệ'], ['MISSING', 'Không còn tồn tại']])}
          {select('sortBy', 'Sắp xếp', [['relevance', 'Độ liên quan'], ['lemma', 'Dạng từ'], ['updatedAt', 'Lần cập nhật']], 'relevance')}
          {select('sortOrder', 'Thứ tự', [['ASC', 'Tăng dần'], ['DESC', 'Giảm dần'], ['asc', 'Tăng dần'], ['desc', 'Giảm dần']], 'ASC')}
          {select('pageSize', 'Số kết quả mỗi trang', [['20', '20'], ['50', '50'], ['100', '100'], ...(params.has('pageSize') && /^([1-9]|[1-9][0-9]|100)$/.test(params.get('pageSize')!) ? [[params.get('pageSize')!, params.get('pageSize')!] as const].filter(([id]) => !['20', '50', '100'].includes(id)) : [])], '50')}
        </div>
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Tìm kiếm</Button>
          <Button type="button" variant="outline" onClick={() => onNavigate('/search?browse=1')}>Duyệt kho từ</Button>
          <Button type="button" variant="outline" onClick={() => onNavigate('/search?browse=1')}>Xóa bộ lọc</Button>
        </div>
      </form>
    </CardContent></Card>
    {params.get('notice') === 'cursorExpired' && <p role="status">Trang đã hết hạn do dữ liệu hoặc truy vấn thay đổi. Đã bắt đầu lại từ trang đầu và giữ bộ lọc.</p>}
    {!active && <p role="status">Nhập nghĩa tiếng Việt hoặc dạng từ, chọn bộ lọc, hoặc bấm Duyệt kho từ.</p>}
    {(view.loading || cursorExpired) && <div className="min-h-32 rounded-md bg-muted p-4 space-y-3"><p role="status" aria-live="polite">Đang tải kết quả…</p><div aria-hidden="true" aria-busy="true" className="space-y-3"><div className="h-5 w-1/2 rounded bg-border" /><div className="h-5 rounded bg-border" /></div></div>}
    {view.error && !cursorExpired && <ReadRecovery error={view.error} onRetry={() => setRetry(value => value + 1)} />}
    {view.data && <>
      <p role="status" aria-live="polite">{view.data.data.length} kết quả trên trang này. {!query.has('meaningVi') && !query.has('lemma') && 'Đang duyệt kho từ.'}</p>
      {view.data.data.length === 0 ? <p>Không tìm thấy dạng từ phù hợp. Thử đổi truy vấn hoặc xóa bộ lọc.</p> :
        <ul aria-label="Kết quả tìm kiếm" className="space-y-3 list-none p-0">
          {view.data.data.map(form => <li key={form.id} className="min-w-0"><Card><CardContent className="pt-6 space-y-2 break-words">
            <h2 className="font-semibold text-xl"><LocalLink href={`/word-forms/${encodeURIComponent(form.id)}?returnTo=${encodeURIComponent(path)}`} onNavigate={onNavigate}>{form.lemma}</LocalLink></h2>
            <p>{form.partOfSpeech} · {verificationLabels[form.verificationSummary]}</p>
            <p lang="vi">{form.meaningViMatch || 'Không có nghĩa tiếng Việt khớp.'}</p>
            <p>Ngày ghi chú: {form.noteDates.length ? form.noteDates.join(', ') : 'Không có ngày nguồn hợp lệ'}</p>
            <p className="text-sm text-muted-foreground">Cập nhật: <time dateTime={form.updatedAt}>{form.updatedAt}</time></p>
          </CardContent></Card></li>)}
        </ul>}
      <div className="flex flex-wrap gap-3">
        {params.has('cursor') && <Button variant="outline" onClick={() => change('cursor', '')}>Trang đầu</Button>}
        {view.data.pagination.hasMore && view.data.pagination.nextCursor && <Button onClick={() => change('cursor', view.data!.pagination.nextCursor!)}>Trang tiếp</Button>}
      </div>
    </>}
  </section>;
}
