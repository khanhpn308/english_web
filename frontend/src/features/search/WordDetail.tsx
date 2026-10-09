import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import type { components } from '@/shared/api/generated';
import { LocalLink, ReadRecovery, isObject, isVerification, isWordForm, useLocalRead, verificationLabels, type Navigate } from './SearchPage';

type Detail = components['schemas']['WordFormDetail'];
const sourceLabels = { VALID: 'Nguồn hợp lệ', INVALID: 'Nguồn không hợp lệ', MISSING: 'Nguồn không còn tồn tại' } satisfies Record<Detail['sourceRefs'][number]['status'], string>;

function isDetail(value: unknown): value is Detail {
  if (!isWordForm(value) || !isObject(value) || typeof value.familyId !== 'string') return false;
  const meaningsValid = (meanings: unknown) => Array.isArray(meanings) && meanings.every(meaning => isObject(meaning)
    && typeof meaning.text === 'string' && typeof meaning.language === 'string' && isVerification(meaning.verificationStatus));
  return meaningsValid(value.meaningsEn) && meaningsValid(value.meaningsVi)
    && Array.isArray(value.examples) && value.examples.every(example => isObject(example) && typeof example.english === 'string'
      && typeof example.vietnamese === 'string' && isVerification(example.verificationStatus))
    && Array.isArray(value.sourceRefs) && value.sourceRefs.every(source => isObject(source) && typeof source.sourceId === 'string'
      && typeof source.noteDate === 'string' && (source.status === 'VALID' || source.status === 'INVALID' || source.status === 'MISSING'))
    && (value.ipaUs === null || typeof value.ipaUs === 'string') && (value.cambridgeUrl === null || typeof value.cambridgeUrl === 'string')
    && (value.card === null || (isObject(value.card) && typeof value.card.id === 'string' && typeof value.card.state === 'string'
      && (value.card.dueAt === null || typeof value.card.dueAt === 'string')));
}

export function WordDetail({ wordFormId, path, onNavigate }: { wordFormId: string; path: string; onNavigate: Navigate }) {
  useEffect(() => { document.querySelector<HTMLHeadingElement>('#main-content h1')?.focus(); }, []);
  const [retry, setRetry] = useState(0);
  let decodedId: string | null;
  try { decodedId = decodeURIComponent(wordFormId); } catch { decodedId = null; }
  const view = useLocalRead<Detail>(decodedId ? `/api/v1/word-forms/${encodeURIComponent(decodedId)}` : null, retry, isDetail);
  const returnTo = new URLSearchParams(path.includes('?') ? path.slice(path.indexOf('?') + 1) : '').get('returnTo');
  // Only our own search route can be a return target, including after reload.
  const back = returnTo && /^\/search(?:\?[^#]*)?$/.test(returnTo) ? returnTo : '/search';
  const form = view.data;
  const activeSource = form?.sourceRefs.some(source => source.status === 'VALID');
  return <section aria-label="Dạng từ đã lưu" className="space-y-4 min-w-0 break-words">
    <LocalLink href={back} onNavigate={onNavigate}>Quay lại kết quả tìm kiếm</LocalLink>
    {!decodedId && <p role="alert">Địa chỉ dạng từ không hợp lệ.</p>}
    {view.loading && <p role="status" aria-live="polite" className="min-h-32 bg-muted rounded-md p-4">Đang tải chi tiết…</p>}
    {view.error && <ReadRecovery error={view.error} onRetry={() => setRetry(value => value + 1)} />}
    {form && <>
      <Card><CardContent className="pt-6 space-y-3">
        <h2 className="text-2xl font-semibold">{form.lemma}</h2>
        <p>{form.partOfSpeech} · {verificationLabels[form.verificationSummary]}</p>
        <dl className="space-y-2">
          <div><dt className="font-medium">Cập nhật</dt><dd><time dateTime={form.updatedAt}>{form.updatedAt}</time></dd></div>
          <div><dt className="font-medium">Phiên bản dạng từ</dt><dd>{form.revision}</dd></div>
          {form.card && <div><dt className="font-medium">Thẻ ôn tập</dt><dd>{form.card.state}{form.card.dueAt && <> · Đến hạn: <time dateTime={form.card.dueAt}>{form.card.dueAt}</time></>}</dd></div>}
        </dl>
      </CardContent></Card>
      <section aria-labelledby="source-heading" className="space-y-2">
        <h2 id="source-heading" className="text-xl font-semibold">Nguồn và ngày ghi chú</h2>
        {!activeSource && <p role="alert">Không có nguồn hợp lệ. Nội dung học hiện tại không khả dụng cho đến khi nguồn được khôi phục.</p>}
        {form.sourceRefs.length ? <ul className="space-y-2">{form.sourceRefs.map(source => <li key={`${source.sourceId}:${source.noteDate}`}>
          <time dateTime={source.noteDate}>{source.noteDate}</time> · {sourceLabels[source.status]}
        </li>)}</ul> : <p>Không có nguồn được liên kết.</p>}
      </section>
      {activeSource && <>
        <section aria-labelledby="meaning-heading" className="space-y-3">
          <h2 id="meaning-heading" className="text-xl font-semibold">Nghĩa</h2>
          {(['meaningsVi', 'meaningsEn'] as const).map(key => <div key={key}><h3 className="font-medium">{key === 'meaningsVi' ? 'Tiếng Việt' : 'Tiếng Anh'}</h3>
            {form[key].length ? <ul>{form[key].map((meaning, index) => <li key={index} lang={key === 'meaningsVi' ? 'vi' : 'en'}>{meaning.text} · <span lang="vi">{verificationLabels[meaning.verificationStatus]}</span></li>)}</ul> : <p>Chưa có nghĩa.</p>}
          </div>)}
        </section>
        <section aria-labelledby="example-heading" className="space-y-2">
          <h2 id="example-heading" className="text-xl font-semibold">Ví dụ</h2>
          {form.examples.length ? <ul className="space-y-3">{form.examples.map((example, index) => <li key={index}><p lang="en">{example.english}</p><p lang="vi">{example.vietnamese}</p><p>{verificationLabels[example.verificationStatus]}</p></li>)}</ul> : <p>Chưa có ví dụ.</p>}
        </section>
        <p>IPA Mỹ: {form.ipaUs ?? 'Chưa có phiên âm'}</p>
        {form.cambridgeUrl ? <CambridgeLink value={form.cambridgeUrl} /> : <p>Chưa có liên kết từ điển.</p>}
      </>}
    </>}
  </section>;
}

function CambridgeLink({ value }: { value: string }) {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && url.hostname === 'dictionary.cambridge.org' && !url.username && !url.password && !url.port) {
      return <a href={url.href} rel="noreferrer" className="text-primary underline break-words focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Từ điển Cambridge</a>;
    }
  } catch { /* Untrusted stored URL remains unavailable. */ }
  return <p>Liên kết từ điển không hợp lệ.</p>;
}
