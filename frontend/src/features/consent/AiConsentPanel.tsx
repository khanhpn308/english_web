import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AiPolicyDisclosure, useAiConsent } from './AiConsentGate';

export function AiConsentPanel() {
  const consent = useAiConsent();
  const { refresh } = consent;
  useEffect(() => { void refresh(); }, [refresh]);
  return <section id="ai-consent" aria-labelledby="ai-consent-heading" className="min-w-0">
    <Card aria-busy={consent.loading || consent.pending}>
      <CardHeader><CardTitle><h2 id="ai-consent-heading" className="m-0 text-xl">Quyền gửi dữ liệu AI</h2></CardTitle></CardHeader>
      <CardContent className="space-y-4 min-w-0">
        <p aria-live="polite" aria-atomic="true">
          {consent.loading ? 'Đang đọc quyền AI' : consent.view ? `Trạng thái: ${consent.view.state}` : 'Chưa xác định quyền AI'}
          {consent.view && ` · Revision ${consent.view.revision}`}
        </p>
        <p>{consent.canRequestAi ? 'Quyền AI hiện tại đã được xác nhận. Mỗi thao tác vẫn kiểm tra lại quyền, kết nối và hạn mức.' : 'Các thao tác AI mới đang bị tắt. Bạn vẫn có thể học cục bộ.'}</p>
        {consent.view?.lastChoiceAt && <p>Lựa chọn gần nhất: <time dateTime={consent.view.lastChoiceAt}>{consent.view.lastChoiceAt}</time></p>}
        {!consent.loading && !consent.policyReady && <p>Chưa hoàn tất chính sách AI</p>}
        {Array.isArray(consent.view?.policy?.blockedReasons) && consent.view.policy.blockedReasons.length > 0
          ? <p>Lý do: {consent.view.policy.blockedReasons.join(', ')}</p> : null}
        {consent.policyReady && consent.view?.policy && <AiPolicyDisclosure policy={consent.view.policy} />}
        <p aria-live="polite" aria-atomic="true">{consent.message}</p>
        {consent.error && <p role="alert">{consent.error}</p>}
        {consent.operationId && <details className="text-sm break-words">
          <summary>Chi tiết hỗ trợ</summary><p>Mã thao tác: {consent.operationId}</p>
        </details>}
        <p className="text-sm text-muted-foreground">Yêu cầu đã gửi có thể vẫn hoàn tất; thao tác này không xóa dữ liệu đã gửi hoặc dữ liệu học trên máy.</p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" disabled={consent.pending || consent.loading} onClick={() => void consent.review()}>Xem chính sách AI</Button>
          <Button type="button" variant="outline" disabled={consent.pending} onClick={() => void consent.refresh()}>Đọc lại trạng thái</Button>
          <Button type="button" variant="destructive" className="whitespace-normal h-auto py-2" disabled={consent.pending} onClick={() => void consent.revoke()}>Rút lại quyền gửi dữ liệu AI</Button>
          {consent.unresolved && <Button type="button" variant="outline" disabled={consent.pending} onClick={() => void consent.retry()}>Thử lại cùng thao tác</Button>}
        </div>
      </CardContent>
    </Card>
  </section>;
}
