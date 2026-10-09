// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { WordDetail } from './WordDetail';
import type { components } from '@/shared/api/generated';

type Detail = components['schemas']['WordFormDetail'];
type SourcePage = components['schemas']['Page_SourceFile_'];
type MutationResult = components['schemas']['WordFormMutationResult'];

const detail: Detail = {
  id: 'form_synthetic', familyId: 'family_synthetic', lemma: 'robust', partOfSpeech: 'ADJECTIVE',
  meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'VERIFIED' }],
  meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }],
  examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }],
  ipaUs: null, cambridgeUrl: null,
  sourceRefs: [{ sourceId: 'source_synthetic', noteDate: '2026-10-09', status: 'VALID' }],
  card: null, revision: 1, updatedAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED', meaningViMatch: 'vững chắc', noteDates: ['2026-10-09']
};

const sourcePage: SourcePage = {
  data: [{ id: 'source_synthetic', relativePath: '26-10-2009.md', noteDate: '2026-10-09', status: 'VALID', revision: 7, etag: '"source-fixture-r7"' }],
  pagination: { hasMore: false, pageSize: 50 }, sort: { by: 'updatedAt', direction: 'DESC' }
};

const mutationSuccess: MutationResult = { wordForm: { ...detail, revision: 2 }, operationId: 'op_test', sourceRevision: 8 };

const json = (body: unknown, status = 200, headers = {}) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
const failure = (code: string, status = 503, details = {}) => json({ error: { code, message: 'backend exception', requestId: 'req_test', details } }, status);

let root: Root;
let host: HTMLDivElement;
let path: string;
let mockFetch: (url: string, init: RequestInit) => Promise<Response>;
let calls: { url: string; method: string; body?: string; headers?: any }[];

async function mount() {
  await act(async () => root.render(<WordDetail wordFormId="form_synthetic" path="/word-forms/form_synthetic?returnTo=%2Fsearch" onNavigate={vi.fn()} />));
}

async function click(label: string) {
  const target = [...host.querySelectorAll('button')].find(button => button.textContent === label);
  if (!target) throw new Error(`Missing button ${label}`);
  await act(async () => target.click());
}

async function editField(labelOrPlaceholder: string, value: string) {
  await act(async () => {
    // simplified selector assuming it's the first input next to a label or just finding inputs
    const inputs = [...host.querySelectorAll('input')];
    // Find input by seeing if it has the current value or something else
    // We can just get input by value for this test
    const input = inputs.find(i => i.value === labelOrPlaceholder);
    if (!input) throw new Error('Missing input');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  path = '/word-forms/form_synthetic'; calls = [];
  mockFetch = async (url) => {
    if (url.includes('/sources')) return json(sourcePage);
    if (url.includes('/word-forms/')) return json(detail);
    return json({});
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, method: init?.method || 'GET', body: init?.body as string, headers: init?.headers });
    return mockFetch(url, init);
  }));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

describe('T030 Edit Form', () => {
  it('loads editable values and allows successful PATCH with preconditions', async () => {
    await mount();
    expect(host.textContent).toContain('Chỉnh sửa');
    
    // Setup for edit
    let patched = false;
    mockFetch = async (url, init) => {
      if (url.includes('/sources')) return json(sourcePage);
      if (url.includes('/word-forms/form_synthetic') && init?.method === 'PATCH') {
        patched = true;
        const body = JSON.parse(init.body as string);
        expect(body.meaningsVi[0].text).toBe('vững chắc được sửa');
        expect(init.headers).toHaveProperty('If-Match', '"source-fixture-r7"');
        return json(mutationSuccess);
      }
      if (url.includes('/word-forms/')) return json({ ...detail, meaningsVi: [{ text: 'vững chắc được sửa', language: 'vi', verificationStatus: 'UNVERIFIED' }] });
      return json({});
    };

    await click('Chỉnh sửa');
    expect(host.textContent).toContain('Chỉnh sửa: robust');
    
    await editField('vững chắc', 'vững chắc được sửa');
    await click('Lưu thay đổi');

    expect(patched).toBe(true);
    expect(host.textContent).toContain('vững chắc được sửa');
    // Success returns to Detail view
    expect(host.textContent).not.toContain('Lưu thay đổi');
  });

  it('preserves draft on 409 conflict and shows dialog', async () => {
    await mount();
    
    let isPatch = false;
    mockFetch = async (url, init) => {
      if (url.includes('/sources')) return json(sourcePage);
      if (url.includes('/word-forms/form_synthetic') && init?.method === 'PATCH') {
        isPatch = true;
        return failure('REVISION_CONFLICT', 409, { kind: 'CONFLICT', currentRevision: 8 });
      }
      if (url.includes('/word-forms/')) return json(detail);
      return json({});
    };

    await click('Chỉnh sửa');
    await editField('vững chắc', 'vững chắc được sửa');
    await click('Lưu thay đổi');

    expect(isPatch).toBe(true);
    expect(host.textContent).toContain('Xung đột dữ liệu');
    expect(host.textContent).toContain('phiên bản hiện tại trên máy chủ: 8');

    // Dismiss dialog by choosing to keep draft and reload source
    const reloadSourceResponse = {
      ...sourcePage,
      data: [{ ...sourcePage.data[0], revision: 8, etag: '"source-fixture-r8"' }]
    };
    mockFetch = async (url) => url.includes('/sources') ? json(reloadSourceResponse) : json({});
    
    await click('Cập nhật mã phiên bản để lưu đè');
    
    // Dialog closes, draft still shows the edited text
    expect(host.textContent).not.toContain('Xung đột dữ liệu');
    const input = [...host.querySelectorAll('input')].find(i => i.value === 'vững chắc được sửa');
    expect(input).toBeDefined();
    
    // We updated source revision, should now show 8
    expect(host.textContent).toContain('Mã nguồn: 8');
  });

  it('maps backend field errors correctly', async () => {
    await mount();
    mockFetch = async (url, init) => {
      if (url.includes('/sources')) return json(sourcePage);
      if (url.includes('/word-forms/form_synthetic') && init?.method === 'PATCH') {
        return failure('VALIDATION_ERROR', 422, { kind: 'FIELD_ERRORS', fields: [{ field: 'meaningsVi', reason: 'Too long' }] });
      }
      if (url.includes('/word-forms/')) return json(detail);
      return json({});
    };

    await click('Chỉnh sửa');
    await click('Lưu thay đổi');

    expect(host.textContent).toContain('Dữ liệu không hợp lệ.');
    expect(host.textContent).toContain('meaningsVi: Too long');
  });

  it('handles unknown operation outcome safely without resubmission', async () => {
    await mount();
    let networkError = true;
    mockFetch = async (url, init) => {
      if (url.includes('/sources')) return json(sourcePage);
      if (url.includes('/word-forms/form_synthetic') && init?.method === 'PATCH') {
        if (networkError) {
          networkError = false; // next time works if retry, but we shouldn't auto retry
          throw new TypeError('Failed to fetch');
        }
      }
      if (url.includes('/word-forms/')) return json(detail);
      return json({});
    };

    await click('Chỉnh sửa');
    await click('Lưu thay đổi');

    // Should show error but keep draft, no second automatic PATCH
    expect(host.textContent).toContain('Lỗi mạng hoặc máy chủ. Bản nháp của bạn vẫn được giữ.');
    const patches = calls.filter(c => c.method === 'PATCH');
    expect(patches.length).toBe(1);
  });
});
