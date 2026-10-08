import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ApiError, apiClient, getETag } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';

type View = components['schemas']['AiConsentView'];
type Policy = components['schemas']['AiDisclosurePolicy'];
type Receipt = components['schemas']['AiConsentMutationResult'];
const endpoint = '/api/v1/ai-consent';
const scopes = ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'];
const states = ['NOT_GRANTED', 'GRANTED', 'REVOKED', 'STALE'];
const text = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const exact = (value: unknown, expected: string[]): boolean => Array.isArray(value) &&
  value.length === expected.length && expected.every(item => value.filter(entry => entry === item).length === 1);

// The generated DTO is a compile-time interface; fetch does not validate JSON.
function readyPolicy(policy: Policy | null): policy is Policy {
  return !!policy && /^[a-z0-9][a-z0-9._-]{0,79}$/.test(policy.version) &&
    /^[a-f0-9]{64}$/.test(policy.digest) && policy.reviewStatus === 'READY' &&
    [policy.disclosureText, policy.retentionStatement, policy.regionStatement,
      policy.costQuotaStatement, policy.withdrawalStatement].every(text) &&
    Array.isArray(policy.dataCategories) && policy.dataCategories.length > 0 &&
    new Set(policy.dataCategories).size === policy.dataCategories.length &&
    policy.dataCategories.every(category => ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'].includes(category)) &&
    Array.isArray(policy.recipients) && policy.recipients.length > 0 && policy.recipients.every(text) &&
    exact(policy.scopes, scopes) && Array.isArray(policy.blockedReasons) && policy.blockedReasons.length === 0 &&
    Array.isArray(policy.dispatchRules) && policy.dispatchRules.length === 3 && scopes.every(scope =>
      policy.dispatchRules.filter(rule => rule && rule.scope === scope &&
        rule.providerLabel === 'Antigravity/Google' && rule.modelId === 'gemini-3.8-flash-high' &&
        rule.route === 'primary' && rule.billingMode === 'configured-account').length === 1);
}
function validView(view: View): boolean {
  return !!view && states.includes(view.state) && Number.isSafeInteger(view.revision) && view.revision >= 0 &&
    typeof view.canRequestAi === 'boolean' &&
    (view.acceptedPolicyVersion === null || text(view.acceptedPolicyVersion)) &&
    (view.acceptedPolicyDigest === null || text(view.acceptedPolicyDigest)) &&
    (view.lastChoiceAt === null || (text(view.lastChoiceAt) &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(view.lastChoiceAt) && Number.isFinite(Date.parse(view.lastChoiceAt)))) &&
    (view.state === 'NOT_GRANTED' || (view.revision > 0 && view.lastChoiceAt !== null)) &&
    (view.policy === null || (typeof view.policy === 'object' && text(view.policy.version) && text(view.policy.digest)));
}
type Intent = { key: string; baseRevision: number; receipt?: Receipt } & (
  { method: 'PUT'; etag: string; policyVersion: string; policyDigest: string } | { method: 'DELETE' }
);
interface ConsentContextValue {
  view: View | null; loading: boolean; pending: boolean; error: string | null; message: string;
  unresolved: 'PUT' | 'DELETE' | null; policyReady: boolean; canRequestAi: boolean;
  operationId: string | null;
  refresh: () => Promise<View | null>; review: () => Promise<void>;
  revoke: () => Promise<void>; retry: () => Promise<void>; requestPermission: (onAuthorized: () => void) => Promise<boolean>;
}
const ConsentContext = createContext<ConsentContextValue | null>(null);
export function useAiConsent(): ConsentContextValue {
  const value = useContext(ConsentContext);
  if (!value) throw new Error('AiConsentProvider is required');
  return value;
}

export function AiPolicyDisclosure({ policy }: { policy: Policy }) {
  const fields = [
    ['Phiên bản chính sách', policy.version], ['Digest chính sách', policy.digest],
    ['Dữ liệu gửi', policy.dataCategories.join(', ')], ['Bên nhận dữ liệu', policy.recipients.join(', ')],
    ['Phạm vi AI', policy.scopes.join(', ')], ['Hạn mức, quyền sử dụng và chi phí', policy.costQuotaStatement],
    ['Giới hạn lưu giữ', policy.retentionStatement], ['Giới hạn vùng xử lý', policy.regionStatement],
    ['Giới hạn rút quyền', policy.withdrawalStatement],
  ];
  return <div className="space-y-4 min-w-0 text-sm">
    <p className="whitespace-pre-wrap break-words">{policy.disclosureText}</p>
    <dl className="space-y-3">
      {fields.map(([label, value]) => <div key={label}>
        <dt className="font-semibold">{label}</dt><dd className="m-0 break-words text-muted-foreground">{value}</dd>
      </div>)}
    </dl>
    <ul className="space-y-3 pl-5">
      {policy.dispatchRules.map(rule => <li key={rule.scope}>
        <span className="font-semibold">{rule.scope}</span>
        <dl className="space-y-1">
          {[[ 'Nhà cung cấp', rule.providerLabel ], [ 'Model', rule.modelId ],
            [ 'Tuyến xử lý', rule.route ], [ 'Chế độ thanh toán', rule.billingMode ]].map(([label, value]) =>
            <div key={label}><dt className="inline font-medium">{label}: </dt><dd className="inline m-0 break-words">{value}</dd></div>)}
        </dl>
      </li>)}
    </ul>
  </div>;
}

export function AiConsentProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<View | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [unresolved, setUnresolved] = useState<'PUT' | 'DELETE' | null>(null);
  const [policyReady, setPolicyReady] = useState(false);
  const [canRequestAi, setCanRequestAi] = useState(false);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState<{ version: string; digest: string; etag: string } | null>(null);
  const [etag, setEtag] = useState<string | undefined>(undefined);
  const [operationId, setOperationId] = useState<string | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const current = useRef<View | null>(null);
  const currentEtag = useRef<string | undefined>(undefined);
  const eligible = useRef(false);
  const generation = useRef(0);
  const busy = useRef(false);
  const intent = useRef<Intent | null>(null);
  const alive = useRef(true);
  const channel = useRef<BroadcastChannel | null>(null);
  const digests = useRef(new Map<string, string>());
  const invalidVersions = useRef(new Set<string>());
  const readController = useRef<AbortController | null>(null);

  const disable = useCallback(() => {
    generation.current += 1;
    eligible.current = false;
    currentEtag.current = undefined;
    setEtag(undefined);
    setPolicyReady(false);
    setCanRequestAi(false);
    readController.current?.abort();
  }, []);

  const refresh = useCallback(async (): Promise<View | null> => {
    if (busy.current) return null;
    disable();
    const token = generation.current;
    const controller = new AbortController(); readController.current = controller;
    setLoading(true);
    if (!intent.current) setMessage('');
    try {
      const next = await apiClient<View>(endpoint, { cache: 'no-store', signal: controller.signal });
      if (!alive.current || token !== generation.current) return null;
      if (!validView(next)) throw new Error('Invalid consent response');
      if (!getETag(next)) throw new Error('Missing consent ETag');
      const policy = next.policy;
      if (policy) {
        const oldDigest = digests.current.get(policy.version);
        if ((oldDigest && oldDigest !== policy.digest) ||
          (next.acceptedPolicyVersion === policy.version && next.acceptedPolicyDigest !== policy.digest)) {
          invalidVersions.current.add(policy.version);
        }
        digests.current.set(policy.version, policy.digest);
      }
      const ready = readyPolicy(policy) && !invalidVersions.current.has(policy.version);
      const granted = next.state === 'GRANTED' && next.canRequestAi && ready &&
        next.acceptedPolicyVersion === policy.version && next.acceptedPolicyDigest === policy.digest &&
        next.revision > 0 && next.lastChoiceAt !== null;
      // Invalid policy evidence may only remove permission; it never creates a grant.
      const display = next.state === 'GRANTED' && !granted ? { ...next, state: 'STALE' as const, canRequestAi: false } : next;
      current.current = display; currentEtag.current = getETag(next);
      setEtag(currentEtag.current);
      setView(display); setPolicyReady(ready); setError(null);
      const active = intent.current;
      if (active) {
        const minimum = active.receipt?.appliedRevision ?? active.baseRevision + 1;
        const hasRevisionEvidence = !!active.receipt || active.baseRevision >= 0;
        const reconciled = hasRevisionEvidence && next.revision >= minimum && (active.method === 'DELETE'
          ? next.state === 'REVOKED' && !next.canRequestAi && next.acceptedPolicyVersion === null && next.acceptedPolicyDigest === null
          : granted && next.acceptedPolicyVersion === active.policyVersion && next.acceptedPolicyDigest === active.policyDigest);
        if (reconciled) {
          intent.current = null; setUnresolved(null);
          setMessage(active.method === 'DELETE' ? 'Đã chặn các yêu cầu AI mới' : 'Đã lưu quyền gửi dữ liệu AI. Hãy bấm lại thao tác AI khi bạn muốn gửi.');
          if (active.method === 'PUT') setOpen(false);
        } else if (active.method === 'PUT' && active.receipt && next.revision > active.receipt.appliedRevision) {
          intent.current = null; setUnresolved(null); setShown(null);
          setMessage('Lựa chọn đã thay đổi sau thao tác trước. Hãy đọc lại chính sách và chọn lại.');
        } else {
          setUnresolved(active.method);
          setMessage(active.method === 'DELETE' ? 'Chưa xác nhận rút quyền' : 'Chưa xác nhận đồng ý. Trạng thái hiện tại có thể đã thay đổi.');
        }
      }
      eligible.current = granted && !intent.current;
      setCanRequestAi(eligible.current);
      return display;
    } catch (failure) {
      if (!alive.current || token !== generation.current) return null;
      if (intent.current) setMessage(intent.current.method === 'DELETE'
        ? 'Chưa xác nhận rút quyền' : 'Chưa xác nhận đồng ý');
      setError(failure instanceof ApiError
        ? `Không đọc được quyền AI (${failure.code}). Mã yêu cầu: ${failure.requestId}`
        : 'Không đọc được quyền AI. Kiểm tra API cục bộ rồi đọc lại trạng thái.');
      return null;
    } finally {
      if (alive.current && token === generation.current) setLoading(false);
    }
  }, [disable]);

  useEffect(() => {
    alive.current = true;
    const invalidate = () => { disable(); void refresh(); };
    const visibility = () => {
      if (document.visibilityState === 'hidden') disable(); else invalidate();
    };
    window.addEventListener('focus', invalidate);
    document.addEventListener('visibilitychange', visibility);
    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel('ai-consent-invalidation-v1');
      channel.current.onmessage = invalidate;
    }
    return () => {
      alive.current = false; generation.current += 1; readController.current?.abort();
      window.removeEventListener('focus', invalidate);
      document.removeEventListener('visibilitychange', visibility);
      channel.current?.close(); channel.current = null;
    };
  }, [disable, refresh]);

  const review = async () => {
    if (!open) returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const next = await refresh();
    if (!next || next !== current.current || busy.current || !alive.current) return;
    const etag = currentEtag.current;
    setShown(readyPolicy(next.policy) && !invalidVersions.current.has(next.policy.version) && etag
      ? { version: next.policy.version, digest: next.policy.digest, etag } : null);
    setOpen(true);
  };

  const perform = async (active: Intent) => {
    if (busy.current) return;
    busy.current = true; intent.current = active; disable();
    setPending(true); setLoading(false); setError(null); setUnresolved(active.method);
    setMessage(active.method === 'DELETE' ? 'Đang rút quyền. Các thao tác AI mới đã bị tắt trên tab này.' : 'Đang lưu lựa chọn AI');
    channel.current?.postMessage('invalidate');
    let mutationError: string | null = null;
    let grantRejected = false;
    try {
      const receipt = await apiClient<Receipt>(endpoint, {
        method: active.method,
        headers: { 'Idempotency-Key': active.key, ...(active.method === 'PUT' ? { 'If-Match': active.etag } : {}) },
        ...(active.method === 'PUT' ? { body: JSON.stringify({ policyVersion: active.policyVersion } satisfies components['schemas']['GrantAiConsent']) } : {}),
      });
      if (!receipt || !text(receipt.operationId) || !Number.isSafeInteger(receipt.appliedRevision) || receipt.appliedRevision < 1) {
        throw new Error('Invalid mutation receipt');
      }
      active.receipt = receipt;
      if (alive.current) setOperationId(receipt.operationId);
    } catch (failure) {
      mutationError = failure instanceof ApiError
        ? `Không xác nhận được lựa chọn (${failure.code}). Mã yêu cầu: ${failure.requestId}`
        : 'Kết quả thao tác chưa xác định. Đọc lại trạng thái hoặc thử lại cùng thao tác.';
      // A definitive grant rejection permits a new explicit choice with fresh disclosure.
      if (active.method === 'PUT' && failure instanceof ApiError && failure.status < 500 && failure.code !== 'IDEMPOTENCY_IN_FLIGHT') {
        grantRejected = true;
        intent.current = null;
        if (alive.current) { setShown(null); setUnresolved(null); }
      }
    } finally {
      busy.current = false;
      if (alive.current) {
        setPending(false);
        await refresh();
        if (mutationError && (intent.current || grantRejected)) setError(mutationError);
        channel.current?.postMessage('invalidate');
      }
    }
  };
  const grant = async () => {
    const latest = current.current;
    if (busy.current || intent.current || !shown || !latest || !readyPolicy(latest.policy) ||
      invalidVersions.current.has(shown.version) || currentEtag.current !== shown.etag ||
      latest.policy.version !== shown.version || latest.policy.digest !== shown.digest) {
      setShown(null); setError('Chính sách hoặc quyền AI đã thay đổi. Hãy đọc lại chính sách và chọn lại.'); return;
    }
    await perform({ method: 'PUT', key: crypto.randomUUID(), etag: shown.etag,
      policyVersion: shown.version, policyDigest: shown.digest, baseRevision: latest.revision });
  };
  const revoke = async () => {
    if (busy.current) return;
    await perform(intent.current?.method === 'DELETE' && !intent.current.receipt ? intent.current : {
      method: 'DELETE', key: crypto.randomUUID(), baseRevision: current.current?.revision ?? -1,
    });
  };
  const requestPermission = async (onAuthorized: () => void) => {
    if (busy.current || intent.current) return false;
    const next = await refresh();
    if (next && next === current.current && alive.current && eligible.current && !busy.current && !intent.current) {
      onAuthorized(); return true;
    }
    if (next) await review();
    return false;
  };
  const grantEnabled = policyReady && !loading && !pending && !unresolved && !error && shown &&
    view?.policy?.version === shown.version && view.policy.digest === shown.digest && etag === shown.etag;

  return <ConsentContext.Provider value={{ view, loading, pending, error, message, unresolved, policyReady, canRequestAi, operationId,
    refresh, review, revoke, retry: async () => { if (intent.current) await perform(intent.current); }, requestPermission }}>
    {children}
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto" onOpenAutoFocus={event => {
        event.preventDefault(); title.current?.focus();
      }} onCloseAutoFocus={event => { event.preventDefault(); returnFocus.current?.focus(); }}>
        <DialogHeader>
          <DialogTitle ref={title} tabIndex={-1} className="focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Quyền gửi dữ liệu AI</DialogTitle>
          <DialogDescription>Đọc chính sách trước khi chọn. Đóng hoặc nhấn Escape là chưa đồng ý; bạn vẫn có thể học cục bộ.</DialogDescription>
        </DialogHeader>
        {!policyReady && <p role="alert">Chưa hoàn tất chính sách AI</p>}
        {policyReady && view?.policy && <AiPolicyDisclosure policy={view.policy} />}
        <p aria-live="polite" aria-atomic="true">{message}</p>
        {error && <p role="alert">{error}</p>}
        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>Chưa đồng ý</Button>
          <Button type="button" variant="outline" disabled={pending || loading} onClick={() => void review()}>Đọc lại chính sách</Button>
          {policyReady && shown && <Button type="button" disabled={!grantEnabled} onClick={() => void grant()}>Đồng ý</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </ConsentContext.Provider>;
}

/** A fresh action reads server permission; saving consent never invokes this callback. */
export function AiConsentGate({ children, onAuthorized }: { children: ReactNode; onAuthorized: () => void }) {
  const consent = useAiConsent();
  return <Button type="button" disabled={consent.pending || !!consent.unresolved} onClick={() => {
    void consent.requestPermission(onAuthorized);
  }}>{children}</Button>;
}
