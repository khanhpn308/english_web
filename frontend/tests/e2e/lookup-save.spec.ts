import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { components } from '../../src/shared/api/generated';

type View = components['schemas']['AiConsentView'];
type Preview = components['schemas']['LookupResult'];
const policy: NonNullable<View['policy']> = {
  version: 'synthetic-policy-v1', digest: 'a'.repeat(64), reviewStatus: 'READY',
  disclosureText: 'Synthetic disclosure', recipients: ['Synthetic recipient'],
  dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'],
  retentionStatement: 'Synthetic retention', regionStatement: 'Synthetic region',
  costQuotaStatement: 'Synthetic quota', withdrawalStatement: 'Synthetic withdrawal',
  scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [],
  dispatchRules: (['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'] as const).map(scope => ({
    scope, providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high',
    route: 'primary', billingMode: 'configured-account',
  })),
};
const consent: View = {
  state: 'GRANTED', revision: 1, policy, canRequestAi: true,
  acceptedPolicyVersion: policy.version, acceptedPolicyDigest: policy.digest,
  lastChoiceAt: '2026-10-09T00:00:00Z',
};
const preview: Preview = {
  lookupId: 'lookup_synthetic', operationId: 'op_synthetic', term: 'robust', status: 'PREVIEW',
  provider: 'Antigravity/Google', model: 'gemini-3.8-flash-high', promptVersion: 'lookup-v1',
  createdAt: '2026-10-09T00:00:00Z', verificationSummary: 'UNVERIFIED',
  forms: ['robust', 'robustly', 'robustness'].map<Preview['forms'][number]>((lemma, index) => ({
    formId: `draft_synthetic_${index}`, lemma,
    partOfSpeech: ['ADJECTIVE', 'ADVERB', 'NOUN'][index],
    ipaUs: null, ipaStatus: 'MISSING', cambridgeUrl: null, cambridgeStatus: 'MISSING',
    meaningsEn: [{ text: 'Synthetic meaning', language: 'en', verificationStatus: 'UNVERIFIED' }],
    meaningsVi: [{ text: 'Nghĩa giả lập', language: 'vi', verificationStatus: 'UNVERIFIED' }],
    examples: [{ english: 'Synthetic example.', vietnamese: 'Ví dụ giả lập.', verificationStatus: 'UNVERIFIED' }],
    verificationSummary: 'UNVERIFIED',
  })),
};

for (const mode of ['local', 'remote', 'absent'] as const) {
  test(`T025 ${mode} voice: keyboard playback stays local @a11y`, async ({ page, context }) => {
    await context.addInitScript(voiceMode => {
      const events = new EventTarget();
      const voices = voiceMode === 'absent' ? [] : [{
        lang: 'en-US', localService: voiceMode === 'local', name: 'Synthetic voice',
        voiceURI: 'synthetic-us', default: true,
      }];
      const audio = { spoken: [] as string[], cancelled: 0 };
      Object.defineProperty(window, '__syntheticAudio', { value: audio });
      Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
        getVoices: () => voices,
        speak: (utterance: SpeechSynthesisUtterance) => {
          if (utterance.voice?.lang !== 'en-US' || utterance.voice.localService !== true) {
            throw new Error('Unsafe synthetic voice selection');
          }
          audio.spoken.push(utterance.text);
        },
        cancel: () => { audio.cancelled += 1; },
        addEventListener: events.addEventListener.bind(events),
        removeEventListener: events.removeEventListener.bind(events),
      } });
    }, mode);
    const requests: string[] = [];
    const external: string[] = [];
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.startsWith('/api/')) requests.push(`${request.method()} ${url.pathname}`);
      if (url.origin !== 'http://127.0.0.1:8124') external.push(request.url());
    });
    await context.route('**/api/v1/ai-consent', route => route.fulfill({
      json: consent, headers: { ETag: '"synthetic-consent"' },
    }));
    await context.route('**/api/v1/lookups', route => route.fulfill({ json: preview }));
    await page.goto('/lookup');
    const input = page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true });
    await input.fill('robust'); await input.press('Enter');
    await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả');
    const previewRegion = page.getByRole('region', { name: 'Kết quả xem trước: robust', exact: true });
    await expect(previewRegion).toContainText('Chưa lưu vào Markdown hoặc tạo thẻ ôn tập.');
    await expect(previewRegion).toContainText('Phát âm Mỹ chỉ khả dụng khi trình duyệt có giọng en-US chạy cục bộ.');
    await expect(previewRegion).not.toContainText('Lưu và phát âm sẽ được tích hợp ở bước sau.');
    const audioRegion = page.getByRole('region', { name: 'Phát âm cục bộ', exact: true });
    for (const form of preview.forms) {
      await expect(page.getByRole('button', { name: `Phát âm Mỹ ${form.lemma}`, exact: true })).toHaveCount(1);
      await expect(page.getByRole('button', { name: `Phát âm Mỹ ${form.lemma}`, exact: true })).toBeVisible();
    }
    const before = requests.slice();
    const playback = page.getByRole('button', { name: 'Phát âm Mỹ robust', exact: true });
    if (mode === 'local') {
      await playback.focus(); await page.keyboard.press('Enter');
      const stop = page.getByRole('button', { name: 'Dừng phát âm robust', exact: true });
      await expect(stop).toBeFocused(); await page.keyboard.press('Space');
      await expect(playback).toBeEnabled();
      await playback.press('Enter');
      await page.getByRole('button', { name: 'Phát âm Mỹ robustly', exact: true }).press('Enter');
      expect(await page.evaluate(() => (window as Window & {
        __syntheticAudio: { spoken: string[] };
      }).__syntheticAudio.spoken)).toEqual(['robust', 'robust', 'robustly']);
      const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
      expect(scan.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
    } else {
      await expect(playback).toBeDisabled();
      await expect(audioRegion).toContainText('Không có giọng en-US được xác nhận chạy cục bộ');
      expect(await page.evaluate(() => (window as Window & {
        __syntheticAudio: { spoken: string[] };
      }).__syntheticAudio.spoken)).toEqual([]);
    }
    expect(requests).toEqual(before); expect(external).toEqual([]);
    for (const width of [320, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    }
    if (mode === 'local') {
      const beforeCancel = await page.evaluate(() => (window as Window & {
        __syntheticAudio: { cancelled: number };
      }).__syntheticAudio.cancelled);
      await page.getByRole('link', { name: 'Ôn tập', exact: true }).click();
      expect(await page.evaluate(() => (window as Window & {
        __syntheticAudio: { cancelled: number };
      }).__syntheticAudio.cancelled)).toBeGreaterThan(beforeCancel);
    }
  });
}

type Receipt = components['schemas']['SaveResult'];
type SaveRequest = components['schemas']['SaveWordFormsRequest'];
const source: components['schemas']['SourceFileView'] = {
  id: 'src_synthetic', noteDate: '2026-10-09', revision: 7,
  etag: '"synthetic-source-r7"', status: 'VALID', relativePath: '09-10-2026.md',
};
function receipt(noteDate = source.noteDate, reused = false, sourceRevision = 8): Receipt {
  const sourceId = noteDate === source.noteDate ? source.id : 'src_second_day';
  const cards = preview.forms.map((_, index) => `card_synthetic_${index}`);
  return {
    operationId: noteDate === source.noteDate ? 'op_save_synthetic' : 'op_save_second_day',
    noteDate, sourceId, sourceRevision, sourceEtag: `"synthetic-source-r${sourceRevision}"`, markdownSync: 'COMPLETED',
    savedForms: preview.forms.map((_, index) => ({ id: `wf_synthetic_${index}`, revision: 1 })),
    canonicalForms: preview.forms.map((form, index) => ({
      id: `wf_synthetic_${index}`, familyId: 'family_synthetic', lemma: form.lemma, partOfSpeech: form.partOfSpeech,
      meaningsEn: form.meaningsEn, meaningsVi: form.meaningsVi, examples: form.examples,
      ipaUs: form.ipaUs, cambridgeUrl: form.cambridgeUrl, revision: 1,
      verificationSummary: form.verificationSummary, updatedAt: '2026-10-09T00:00:00Z',
      sourceRefs: [{ sourceId, noteDate, status: 'VALID' }],
      card: { id: cards[index], state: reused ? 'LEARNED' : 'NEW', dueAt: reused ? '2026-10-10T00:00:00Z' : null },
    })),
    createdCardIds: reused ? [] : cards, reusedCardIds: reused ? cards : [],
  };
}
async function openPreview(page: Page) {
  await page.route('**/api/v1/ai-consent', route => route.fulfill({ json: consent, headers: { ETag: '"synthetic-consent"' } }));
  await page.route('**/api/v1/lookups', route => route.fulfill({ json: preview }));
  await page.goto('/lookup');
  await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill('robust');
  await page.getByRole('button', { name: 'Tra cứu', exact: true }).press('Enter');
  await expect(page.locator('#lookup-status')).toContainText('Đã có kết quả');
}
async function readDay(page: Page, noteDate = source.noteDate) {
  const region = page.getByRole('region', { name: 'Lưu bản xem trước để ôn tập', exact: true });
  await region.getByLabel('Ngày học', { exact: true }).fill(noteDate);
  await region.getByRole('button', { name: 'Đọc nguồn', exact: true }).press('Enter');
  await expect(region.getByRole('button', { name: 'Lưu để ôn', exact: true })).toBeEnabled();
  return region;
}

test('T025 keyboard Save waits for a receipt, replays its key, and distinguishes reused cards @a11y', async ({ page }) => {
  const posts: { body: SaveRequest; key: string | undefined; match: string | undefined; none: string | undefined }[] = [];
  let release!: () => void;
  const responseGate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/sources?*', route => {
    const noteDate = new URL(route.request().url()).searchParams.get('noteDate');
    return route.fulfill({ json: { data: noteDate === source.noteDate ? [source] : [],
      pagination: { hasMore: false, nextCursor: null, pageSize: 100 }, sort: { by: 'noteDate', direction: 'ASC' } } });
  });
  await page.route('**/api/v1/operations/op_save_synthetic', route => route.fulfill({ json: {
    operationId: 'op_save_synthetic', kind: 'SAVE', status: 'SUCCEEDED', resultRef: 'op_save_synthetic',
    createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z',
  } }));
  await page.route('**/api/v1/word-forms', async route => {
    const request = route.request(); const headers = request.headers();
    const body = request.postDataJSON() as SaveRequest;
    posts.push({ body, key: headers['idempotency-key'], match: headers['if-match'], none: headers['if-none-match'] });
    if (posts.length === 1) await responseGate;
    const secondDay = body.noteDate !== source.noteDate;
    const result = receipt(body.noteDate, secondDay, secondDay ? 1 : 8);
    await route.fulfill({ status: 201, json: result, headers: { ETag: result.sourceEtag } });
  });
  await openPreview(page);
  const region = await readDay(page);
  const save = region.getByRole('button', { name: 'Lưu để ôn', exact: true });
  await save.press('Enter');
  await expect.poll(() => posts.length).toBe(1);
  await expect(region.getByRole('button', { name: 'Đang lưu…', exact: true })).toBeDisabled();
  await expect(region.getByLabel('Ngày học', { exact: true })).toBeDisabled();
  await expect(region).not.toContainText('Đã lưu để ôn');
  await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill('edited while saving');
  await expect(page.getByRole('button', { name: 'Tra cứu', exact: true })).toBeDisabled();
  await expect(page.getByRole('region', { name: 'Kết quả xem trước: robust', exact: true })).toBeVisible();
  expect(posts[0].body).toEqual({ lookupId: preview.lookupId, noteDate: source.noteDate, sourceId: source.id, sourceRevision: source.revision });
  expect(posts[0].match).toBe(source.etag); expect(posts[0].none).toBeUndefined();
  release();
  await expect(region).toContainText('Đã lưu để ôn');
  await expect(page.locator('#lookup-status')).toContainText('Backend đã xác nhận lưu');
  await expect(page.locator('#lookup-status')).not.toContainText('Chưa lưu');
  await expect(region.getByRole('region', { name: 'Biên nhận lưu' })).toContainText('Thẻ mới: 3. Thẻ dùng lại: 0.');
  await expect(page.getByRole('region', { name: 'Kết quả xem trước: robust', exact: true })).toContainText('Backend đã xác nhận lưu');
  await expect(region.getByRole('button', { name: 'Đã lưu ngày này', exact: true })).toBeDisabled();
  await region.getByRole('button', { name: 'Kiểm tra biên nhận', exact: true }).press('Space');
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[1]).toEqual(posts[0]);
  await expect(region.getByRole('button', { name: 'Kiểm tra biên nhận', exact: true })).toBeVisible();
  const scan = await new AxeBuilder({ page }).withTags(['wcag22aa', 'wcag2aa']).analyze();
  expect(scan.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
  await readDay(page, '2026-10-10');
  await region.getByRole('button', { name: 'Lưu để ôn', exact: true }).press('Enter');
  await expect(region.getByRole('region', { name: 'Biên nhận lưu' })).toContainText('Thẻ mới: 0. Thẻ dùng lại: 3.');
  expect(posts[2].body).toEqual({ lookupId: preview.lookupId, noteDate: '2026-10-10' });
  expect(posts[2].none).toBe('*'); expect(posts[2].match).toBeUndefined(); expect(posts[2].key).not.toBe(posts[0].key);
});

test('T025 stale source requires a fresh read before a new explicit Save', async ({ page }) => {
  let currentSource = source;
  const bodies: SaveRequest[] = []; const keys: (string | undefined)[] = [];
  await page.route('**/api/v1/sources?*', route => route.fulfill({ json: { data: [currentSource],
    pagination: { hasMore: false, nextCursor: null, pageSize: 100 }, sort: { by: 'noteDate', direction: 'ASC' } } }));
  await page.route('**/api/v1/word-forms', route => {
    bodies.push(route.request().postDataJSON() as SaveRequest); keys.push(route.request().headers()['idempotency-key']);
    if (bodies.length === 1) {
      currentSource = { ...source, revision: 8, etag: '"synthetic-source-r8"' };
      return route.fulfill({ status: 409, json: { error: { code: 'REVISION_CONFLICT', message: 'Synthetic conflict', requestId: 'req_conflict',
        details: { kind: 'CONFLICT', resourceType: 'SOURCE', resourceId: source.id, expectedRevision: 7, currentRevision: 8 } } } });
    }
    return route.fulfill({ status: 201, json: receipt(source.noteDate, false, 9) });
  });
  await openPreview(page); const region = await readDay(page);
  await region.getByRole('button', { name: 'Lưu để ôn', exact: true }).click();
  await expect(region).toContainText('revision trong yêu cầu 7, revision hiện tại 8');
  await expect(region.getByRole('button', { name: 'Lưu để ôn', exact: true })).toBeDisabled();
  await expect(region).not.toContainText('Đã lưu để ôn'); expect(bodies).toHaveLength(1);
  await region.getByRole('button', { name: 'Đọc lại nguồn', exact: true }).press('Enter');
  await expect(region.getByRole('button', { name: 'Lưu để ôn', exact: true })).toBeEnabled();
  expect(bodies).toHaveLength(1);
  await region.getByRole('button', { name: 'Lưu để ôn', exact: true }).press('Enter');
  await expect(region).toContainText('Đã lưu để ôn'); expect(bodies[1].sourceRevision).toBe(8); expect(keys[1]).not.toBe(keys[0]);
});

test('T025 lost Save response survives reload and reconciles without another independent mutation', async ({ page }) => {
  const posts: { body: string | null; key: string | undefined }[] = [];
  await page.route('**/api/v1/sources?*', route => route.fulfill({ json: { data: [source],
    pagination: { hasMore: false, nextCursor: null, pageSize: 100 }, sort: { by: 'noteDate', direction: 'ASC' } } }));
  await page.route('**/api/v1/word-forms', route => {
    posts.push({ body: route.request().postData(), key: route.request().headers()['idempotency-key'] });
    return posts.length === 1 ? route.abort('failed') : route.fulfill({ status: 201, json: receipt() });
  });
  await openPreview(page); const region = await readDay(page);
  await region.getByRole('button', { name: 'Lưu để ôn', exact: true }).press('Enter');
  await expect(region).toContainText('Chưa xác định');
  await page.getByLabel('Từ hoặc cụm từ cần tra cứu', { exact: true }).fill('new term');
  await expect(page.getByRole('region', { name: 'Kết quả xem trước: robust', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tra cứu', exact: true })).toBeDisabled();
  await expect(region).not.toContainText('Đã lưu để ôn'); expect(posts).toHaveLength(1);
  await page.reload();
  await expect(region).toContainText('Chưa xác định'); expect(posts).toHaveLength(1);
  await region.getByRole('button', { name: 'Kiểm tra kết quả lưu', exact: true }).press('Enter');
  await expect(region).toContainText('Đã lưu để ôn'); expect(posts).toHaveLength(2); expect(posts[1]).toEqual(posts[0]);
  await expect(region.getByRole('region', { name: 'Biên nhận lưu' })).toContainText('Nghĩa giả lập');
});
