import { test, expect } from '@playwright/test';

test.describe('Quiz Runner', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('/api/v1/health', async (route) => {
      await route.fulfill({
        status: 200,
        json: { status: 'OK', readiness: true, version: '1.0.0', storageStatus: 'OK', bridgeStatus: 'OK' }
      });
    });

    await page.route('/api/v1/ai-consent', async (route) => {
      await route.fulfill({
        status: 200,
        json: { state: 'GRANTED', canRequestAi: true, revision: 1 }
      });
    });

    await page.route('/api/v1/quiz-attempts/attempt-123', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 'attempt-123',
          status: 'IN_PROGRESS',
          questions: [
            { id: 'q1', type: 'MCQ', promptEn: 'MCQ Prompt', options: [{ id: 'opt1', textEn: 'Opt 1' }, { id: 'opt2', textEn: 'Opt 2' }] },
            { id: 'q2', type: 'CLOZE', promptEn: 'CLOZE Prompt' },
            { id: 'q3', type: 'WRITING', promptEn: 'WRITING Prompt', targetLemma: 'apple', rubric: { descriptors: [{ score: 0, textVi: 'Không' }, { score: 1, textVi: 'Một' }, { score: 2, textVi: 'Hai' }, { score: 3, textVi: 'Ba' }, { score: 4, textVi: 'Bốn' }] } }
          ],
          answerPreconditions: [
            { questionId: 'q1', draftRevision: 1, etag: 'etag-q1-1' },
            { questionId: 'q2', draftRevision: 1, etag: 'etag-q2-1' },
            { questionId: 'q3', draftRevision: 1, etag: 'etag-q3-1' }
          ],
          answers: []
        }
      });
    });
  });

  test('loads attempt, restores data, and performs autosave', async ({ page }) => {
    let saveRequests = 0;
    await page.route('/api/v1/quiz-attempts/attempt-123/answers/q2', async (route) => {
      if (route.request().method() === 'PUT') {
        saveRequests++;
        const body = JSON.parse(route.request().postData()!);
        await route.fulfill({
          status: 200,
          headers: { ETag: `etag-q2-${saveRequests + 1}` },
          json: {
            questionId: 'q2',
            answer: body.answer,
            selfScore: null,
            draftRevision: body.draftRevision + 1,
            state: 'DRAFT'
          }
        });
      } else {
        await route.fallback();
      }
    });

    await page.goto('/quiz/attempt-123');
    
    // Check render
    await expect(page.getByRole('heading', { name: 'Làm bài kiểm tra' })).toBeVisible();
    await expect(page.getByText('CLOZE Prompt')).toBeVisible();

    // Type in CLOZE
    const input = page.getByLabel('Câu trả lời:');
    await input.fill('my test answer');
    
    // Blur to trigger immediate save
    await input.blur();

    // Verify it says saved
    await expect(page.locator('text=Đã lưu').first()).toBeVisible();
    expect(saveRequests).toBeGreaterThan(0);
    
    // Check writing self score
    const writingScoreRadio = page.getByLabel('Điểm 4');
    await expect(writingScoreRadio).toBeVisible();
  });

  test('offline behavior preserves error state and allows recovery', async ({ page, context }) => {
    await page.route('/api/v1/quiz-attempts/attempt-offline', async (route) => {
      await route.abort('internetdisconnected');
    });

    await page.goto('/quiz/attempt-offline');
    await expect(page.getByText('Không thể tải bài kiểm tra. Vui lòng kiểm tra kết nối.')).toBeVisible();
    
    // Mock recovery
    await page.route('/api/v1/quiz-attempts/attempt-offline', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 'attempt-offline',
          status: 'IN_PROGRESS',
          questions: [{ id: 'q1', type: 'CLOZE', promptEn: 'CLOZE Prompt' }],
          answerPreconditions: [{ questionId: 'q1', draftRevision: 1, etag: 'etag-1' }],
          answers: []
        }
      });
    });

    await page.getByRole('button', { name: 'Thử lại' }).click();
    await expect(page.getByText('CLOZE Prompt')).toBeVisible();
  });
});
