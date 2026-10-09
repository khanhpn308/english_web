import { useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { components } from '@/shared/api/generated';

type ReviewCard = components['schemas']['ReviewCardView'];
type WordDetail = components['schemas']['WordFormDetail'];
type Rating = components['schemas']['ReviewRequest']['rating'];
interface FlashcardProps {
  card: ReviewCard;
  detail?: WordDetail;
  disabled: boolean;
  onRate: (rating: Rating) => void;
}

export function Flashcard({ card, detail, disabled, onRate }: FlashcardProps) {
  const [revealed, setRevealed] = useState(false);
  const answerId = useId();
  const firstRating = useRef<HTMLButtonElement>(null);
  const reveal = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (revealed && !disabled) firstRating.current?.focus(); }, [disabled, revealed]);
  useEffect(() => { if (!disabled && !revealed) reveal.current?.focus(); }, [disabled, revealed]);
  let dictionaryUrl: string | undefined;
  if (detail?.cambridgeUrl) {
    try {
      const url = new URL(detail.cambridgeUrl);
      if (url.protocol === 'https:' && url.hostname === 'dictionary.cambridge.org' &&
        !url.username && !url.password && !url.port) dictionaryUrl = url.href;
    } catch { dictionaryUrl = undefined; }
  }

  return <Card data-flashcard aria-labelledby={`${answerId}-question`} className="min-w-0">
    <CardHeader>
      <p className="text-sm text-muted-foreground">Nhớ nghĩa tiếng Việt của từ</p>
      <CardTitle><h2 id={`${answerId}-question`} lang="en" className="text-2xl break-words">{card.lemma}</h2></CardTitle>
      <p className="text-sm">{card.state === 'NEW' ? 'Chưa học' : 'Đã học'}
        {card.dueAt && <> · Hạn ôn do máy chủ cung cấp: <time dateTime={card.dueAt}>{card.dueAt}</time></>}
      </p>
      <p className="text-sm break-words">Ngày ghi chú: {card.noteDates.join(', ')}</p>
    </CardHeader>
    <CardContent className="space-y-4 min-w-0 break-words">
      {!revealed && <Button ref={reveal} type="button" className="min-h-11" disabled={disabled || !detail} aria-expanded={false}
        aria-controls={answerId} onClick={() => setRevealed(true)}>Lật thẻ</Button>}
      <div id={answerId}>
      {revealed && detail && <>
        <section aria-label="Nội dung sau khi lật thẻ" className="space-y-4">
          <p>{detail.partOfSpeech} · {detail.verificationSummary}</p>
          <p>{detail.ipaUs ?? 'Không có IPA Mỹ'}</p>
          <h3 className="font-semibold">Nghĩa tiếng Việt</h3>
          {detail.meaningsVi.length ? <ul className="space-y-2">
            {detail.meaningsVi.map((meaning, index) => <li key={index} lang="vi">
              {meaning.text} <span className="text-sm text-muted-foreground">({meaning.verificationStatus})</span>
            </li>)}
          </ul> : <p>Chưa có nghĩa tiếng Việt.</p>}
          <h3 className="font-semibold">Nghĩa tiếng Anh</h3>
          {detail.meaningsEn.length ? <ul className="space-y-2">
            {detail.meaningsEn.map((meaning, index) => <li key={index} lang="en">
              {meaning.text} <span className="text-sm text-muted-foreground">({meaning.verificationStatus})</span>
            </li>)}
          </ul> : <p>Chưa có nghĩa tiếng Anh.</p>}
          <h3 className="font-semibold">Ví dụ</h3>
          {detail.examples.length ? <ul className="space-y-3">
            {detail.examples.map((example, index) => <li key={index}>
              <p lang="en">{example.english}</p><p lang="vi">{example.vietnamese}</p>
              <span className="text-sm text-muted-foreground">{example.verificationStatus}</span>
            </li>)}
          </ul> : <p>Chưa có ví dụ.</p>}
          {dictionaryUrl && <a href={dictionaryUrl} target="_blank" rel="noopener noreferrer"
            referrerPolicy="no-referrer" className="underline text-primary focus-visible:outline focus-visible:outline-ring">
            Nguồn Cambridge của {detail.lemma}
          </a>}
        </section>
        <fieldset disabled={disabled} aria-label="Đánh giá thẻ" className="space-y-3">
          <legend className="font-semibold">Bạn nhớ từ này như thế nào?</legend>
          <div className="flex flex-wrap gap-2">
            {(['AGAIN', 'HARD', 'GOOD', 'EASY'] as const).map((rating, index) =>
              <Button key={rating} ref={index === 0 ? firstRating : undefined} type="button"
                variant="outline" className="min-h-11" disabled={disabled} onClick={() => onRate(rating)}>{rating}</Button>)}
          </div>
        </fieldset>
      </>}
      </div>
    </CardContent>
  </Card>;
}
