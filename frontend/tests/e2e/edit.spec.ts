import { test, expect, type BrowserContext, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type Detail = components['schemas']['WordFormDetail'];
type SourceFile = components['schemas']['SourceFile'];
type PatchWordFormRequest = components['schemas']['PatchWordFormRequest'];
type SourcePage = components['schemas']['Page_SourceFile_'];

const word: Detail = { 
  id: 'form_123', familyId: 'fam_123', lemma: 'robust', partOfSpeech: 'ADJECTIVE', 
  meaningsEn: [{ text: 'strong', language: 'en', verificationStatus: 'VERIFIED' }], 
  meaningsVi: [{ text: 'vững chắc', language: 'vi', verificationStatus: 'UNVERIFIED' }], 
  examples: [{ english: 'A robust design.', vietnamese: 'Một thiết kế vững chắc.', verificationStatus: 'UNVERIFIED' }], 
  ipaUs: '/roʊˈbʌst/', cambridgeUrl: null, 
  sourceRefs: [{ sourceId: 'src_123', noteDate: '2026-10-09', status: 'VALID' }], 
  card: { id: 'card_1', state: 'LEARNING', dueAt: null },
  revision: 1, updatedAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED'
};

const source: SourceFile = {
  id: 'src_123',
  userId: 'user_1',
  path: '2026/10/09/notes.md',
  noteDate: '2026-10-09',
  content: '',
  parsedWordCount: 1,
  status: 'VALID',
  revision: 5,
  etag: 'W/"5"',
  createdAt: '2026-10-09T00:00:00Z',
  updatedAt: '2026-10-09T00:00:00Z',
};

const sourcesCollection: SourcePage = {
  data: [source],
  pagination: { hasMore: false, pageSize: 50, nextCursor: null },
  sort: { by: 'createdAt', direction: 'DESC' }
};

const fail = (route: Route, code: string, status = 503, details?: any) => route.fulfill({ status, json: { error: { code, message: 'Mock Error', requestId: 'req_123', details } } });

async function fixture(context: BrowserContext) {
  const patches: { url: URL, body: PatchWordFormRequest, headers: Record<string, string> }[] = [];
  let form: (route: Route) => Promise<void> = async route => { await route.fulfill({ json: word }); };
  let getSources: (route: Route) => Promise<void> = async route => { await route.fulfill({ json: sourcesCollection }); };
  let patchWord: (route: Route) => Promise<void> = async route => { 
    patches.push({ 
      url: new URL(route.request().url()), 
      body: route.request().postDataJSON() as PatchWordFormRequest,
      headers: route.request().headers(),
    });
    await route.fulfill({ json: { sourceRevision: 6 } }); 
  };

  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:8124') { await route.abort(); return; }
    if (url.pathname.startsWith('/api/v1/word-forms/') && route.request().method() === 'GET') { await form(route); return; }
    if (url.pathname === '/api/v1/sources' && route.request().method() === 'GET') { await getSources(route); return; }
    if (url.pathname.startsWith('/api/v1/word-forms/') && route.request().method() === 'PATCH') { await patchWord(route); return; }
    await route.continue();
  });
  return { 
    patches, 
    form: (handler: typeof form) => { form = handler; }, 
    getSources: (handler: typeof getSources) => { getSources = handler; }, 
    patchWord: (handler: typeof patchWord) => { patchWord = handler; } 
  };
}

test.beforeEach(async ({ page, request }) => {
  const response = await request.post('/_harness/token', { headers: { Origin: 'http://127.0.0.1:8124' } });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  await page.goto(`/bootstrap#token=${body.token}`);
  await expect(page.getByRole('heading', { level: 1, name: 'Tổng quan', exact: true })).toBeVisible();
});

test('successful edit flow with correct preconditions', async ({ page, context }) => {
  const api = await fixture(context);
  
  // Go to search page and select word
  await page.goto('/search?wordFormId=form_123');
  await expect(page.getByRole('heading', { name: 'robust', level: 2 })).toBeVisible();
  
  // Click edit button next to source
  await page.getByRole('button', { name: 'Chỉnh sửa' }).click();
  
  // Check form is populated with canonical editable values
  await expect(page.getByRole('heading', { name: 'Chỉnh sửa: robust' })).toBeVisible();
  const enInput = page.getByDisplayValue('strong');
  const viInput = page.getByDisplayValue('vững chắc');
  const ipaInput = page.getByDisplayValue('/roʊˈbʌst/');
  
  await expect(enInput).toBeVisible();
  await expect(viInput).toBeVisible();
  await expect(ipaInput).toBeVisible();
  
  // Edit a field
  await viInput.fill('vững chắc, mạnh mẽ');
  
  // Save
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  
  // Verify PATCH payload and preconditions
  expect(api.patches).toHaveLength(1);
  const patch = api.patches[0];
  expect(patch.headers['if-match']).toBe('W/"5"');
  expect(patch.headers['idempotency-key']).toBeDefined();
  expect(patch.body.sourceId).toBe('src_123');
  expect(patch.body.sourceRevision).toBe(5);
  expect(patch.body.meaningsVi[0].text).toBe('vững chắc, mạnh mẽ');
  
  // Edit form should close on success (refresh triggers refetch)
  await expect(page.getByRole('heading', { name: 'Chỉnh sửa: robust' })).toBeHidden();
});

test('conflict handling preserves draft and allows reload', async ({ page, context }) => {
  const api = await fixture(context);
  
  let patchCalls = 0;
  api.patchWord(async (route) => {
    patchCalls++;
    if (patchCalls === 1) {
      // First attempt triggers conflict
      await fail(route, 'REVISION_CONFLICT', 409, { kind: 'CONFLICT', currentRevision: 6 });
    } else {
      // Second attempt succeeds
      await route.fulfill({ json: { sourceRevision: 7 } });
    }
  });

  await page.goto('/search?wordFormId=form_123');
  await page.getByRole('button', { name: 'Chỉnh sửa' }).click();
  
  const viInput = page.getByDisplayValue('vững chắc');
  await viInput.fill('draft meaning');
  
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  
  // Dialog opens
  const dialog = page.getByRole('dialog', { name: 'Xung đột phiên bản' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Phiên bản trên máy chủ: 6')).toBeVisible();
  
  // Draft is preserved in background
  await expect(page.getByDisplayValue('draft meaning')).toBeVisible();
  
  // Mock source reload returning new revision
  api.getSources(async (route) => {
    await route.fulfill({ json: { ...sourcesCollection, data: [{ ...source, revision: 6, etag: 'W/"6"' }] } });
  });
  
  // User chooses to reload source
  await dialog.getByRole('button', { name: 'Cập nhật mã phiên bản để lưu đè' }).click();
  
  // Dialog closes, draft still preserved
  await expect(dialog).toBeHidden();
  await expect(page.getByDisplayValue('draft meaning')).toBeVisible();
  
  // Header shows new revision
  await expect(page.getByText('Mã nguồn: 6')).toBeVisible();
  
  // Save again
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  
  // Form closes on success
  await expect(page.getByRole('heading', { name: 'Chỉnh sửa: robust' })).toBeHidden();
});

test('handles validation errors and network errors safely', async ({ page, context }) => {
  const api = await fixture(context);
  
  api.patchWord(async (route) => {
    await fail(route, 'INVALID_ARGUMENT', 400, { 
      kind: 'FIELD_ERRORS', 
      fields: [{ field: 'ipaUs', reason: 'Invalid format' }] 
    });
  });

  await page.goto('/search?wordFormId=form_123');
  await page.getByRole('button', { name: 'Chỉnh sửa' }).click();
  
  // Fill and save
  await page.getByDisplayValue('/roʊˈbʌst/').fill('invalid_ipa');
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  
  // Validation error displayed
  await expect(page.getByText('Dữ liệu không hợp lệ.')).toBeVisible();
  await expect(page.getByText('ipaUs: Invalid format')).toBeVisible();
  
  // Draft preserved
  await expect(page.getByDisplayValue('invalid_ipa')).toBeVisible();
  
  // Test network error
  api.patchWord(async (route) => {
    await route.abort('failed'); // Network error
  });
  
  await page.getByRole('button', { name: 'Lưu thay đổi' }).click();
  
  await expect(page.getByText('Lỗi mạng hoặc máy chủ. Bản nháp của bạn vẫn được giữ.')).toBeVisible();
  await expect(page.getByDisplayValue('invalid_ipa')).toBeVisible();
});

test('handles read-only behavior for invalid sources', async ({ page, context }) => {
  const api = await fixture(context);
  
  // Source is INVALID
  api.form(async (route) => {
    await route.fulfill({ json: { ...word, sourceRefs: [{ sourceId: 'src_123', noteDate: '2026-10-09', status: 'INVALID' }] } });
  });

  await page.goto('/search?wordFormId=form_123');
  await expect(page.getByRole('heading', { name: 'robust', level: 2 })).toBeVisible();
  
  // Edit button should not be present
  await expect(page.getByRole('button', { name: 'Chỉnh sửa' })).toBeHidden();
  await expect(page.getByText('Không có nguồn hợp lệ. Nội dung học hiện tại không khả dụng cho đến khi nguồn được khôi phục.')).toBeVisible();
});

test('accessibility of edit form and conflict dialog', async ({ page, context }) => {
  await fixture(context);
  await page.goto('/search?wordFormId=form_123');
  
  // Edit form a11y
  await page.getByRole('button', { name: 'Chỉnh sửa' }).click();
  await expect(page.getByRole('heading', { name: 'Chỉnh sửa: robust' })).toBeVisible();
  
  let results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
