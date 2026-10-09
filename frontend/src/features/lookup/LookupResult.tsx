import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { components } from '@/shared/api/generated';

type Preview = components['schemas']['LookupResult'];
type Verification = Preview['verificationSummary'];

function VerificationLabel({ status }: { status: Verification }) {
  return <span className="text-sm font-medium text-muted-foreground">
    {status === 'VERIFIED' ? 'VERIFIED · Đã xác minh' : status === 'MISSING' ? 'MISSING · Thiếu dữ liệu' : 'UNVERIFIED · Chưa xác minh'}
  </span>;
}

function sourceLink(raw: string | null): string | null {
  if (!raw || !raw.startsWith('https://dictionary.cambridge.org/dictionary/english/') || /[\\@?#\s\u0000-\u001f\u007f-\u009f]/u.test(raw)) return null;
  try {
    const url = new URL(raw);
    return url.protocol === 'https:' && url.hostname === 'dictionary.cambridge.org' &&
      !url.username && !url.password && !url.port && url.pathname.startsWith('/dictionary/english/')
      ? url.href : null;
  } catch {
    return null;
  }
}

/** Provider text stays text. Only the returned Cambridge reference can become a link. */
export function LookupResult({ preview, savedNoteDate }: { preview: Preview; savedNoteDate?: string }) {
  return <section aria-labelledby="lookup-preview-heading" className="space-y-4 min-w-0 break-words [overflow-wrap:anywhere]">
    <h2 id="lookup-preview-heading" className="m-0 text-xl font-semibold">Kết quả xem trước: {preview.term}</h2>
    <p className="text-sm text-muted-foreground">{savedNoteDate ? `Backend đã xác nhận lưu bản xem trước vào ngày ${savedNoteDate}.` : 'Chỉ xem trước. Chưa lưu vào Markdown hoặc tạo thẻ ôn tập.'} Phát âm Mỹ chỉ khả dụng khi trình duyệt có giọng en-US chạy cục bộ.</p>
    <p><VerificationLabel status={preview.verificationSummary} /></p>
    {preview.forms.length === 0 && <p>Không có dạng từ trong kết quả xem trước.</p>}
    {preview.forms.map(form => {
      const href = sourceLink(form.cambridgeUrl);
      return <Card key={form.formId}>
        <CardHeader>
          <CardTitle><h3 className="m-0 text-lg">{form.lemma}</h3></CardTitle>
          <p className="m-0">Từ loại: {form.partOfSpeech}</p>
          <VerificationLabel status={form.verificationSummary} />
        </CardHeader>
        <CardContent className="space-y-4 min-w-0">
          <p>IPA Mỹ: <span lang="en-US">{form.ipaUs ?? 'Không có IPA Mỹ'}</span>{' '}<VerificationLabel status={form.ipaStatus} /></p>
          <div>
            <p className="font-semibold">Nghĩa tiếng Việt</p>
            {form.meaningsVi.length === 0 && <p>MISSING · Không có nghĩa tiếng Việt</p>}
            <ul className="space-y-2 pl-5">{form.meaningsVi.map((meaning, index) =>
              <li key={index} lang="vi"><span className="whitespace-pre-wrap">{meaning.text}</span>{' '}<VerificationLabel status={meaning.verificationStatus} /></li>)}</ul>
          </div>
          <div>
            <p className="font-semibold">Nghĩa tiếng Anh</p>
            {form.meaningsEn.length === 0 && <p>MISSING · Không có nghĩa tiếng Anh</p>}
            <ul className="space-y-2 pl-5">{form.meaningsEn.map((meaning, index) =>
              <li key={index}><span lang="en" className="whitespace-pre-wrap">{meaning.text}</span>{' '}<VerificationLabel status={meaning.verificationStatus} /></li>)}</ul>
          </div>
          <div>
            <p className="font-semibold">Ví dụ và bản dịch</p>
            {form.examples.length === 0 && <p>MISSING · Không có ví dụ</p>}
            <ol className="space-y-3 pl-5">{form.examples.map((example, index) => <li key={index}>
              <p lang="en" className="m-0 whitespace-pre-wrap">{example.english}</p>
              <p lang="vi" className="m-0 whitespace-pre-wrap">{example.vietnamese}</p>
              <VerificationLabel status={example.verificationStatus} />
            </li>)}</ol>
          </div>
          <div>
            <p>Cambridge: <VerificationLabel status={form.cambridgeStatus} /></p>
            {href ? <a href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"
              className="underline text-primary rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
              {form.cambridgeUrl} <span className="sr-only">, mở tab mới</span>
            </a> : <p>{form.cambridgeUrl ? 'Liên kết không an toàn, không mở được.' : 'Không có liên kết Cambridge'}</p>}
          </div>
        </CardContent>
      </Card>;
    })}
    <details className="text-sm text-muted-foreground">
      <summary className="cursor-pointer rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Nguồn gốc kết quả</summary>
      <dl className="space-y-2">
        {([['Nhà cung cấp', preview.provider], ['Model', preview.model], ['Phiên bản prompt', preview.promptVersion],
          ['Mã tra cứu', preview.lookupId], ['Mã thao tác', preview.operationId], ['Thời điểm tạo', preview.createdAt]]).map(([label, value]) =>
          <div key={label}><dt className="font-semibold">{label}</dt><dd className="m-0">{value}</dd></div>)}
      </dl>
    </details>
  </section>;
}
