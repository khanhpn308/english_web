import { expect, test } from '@playwright/test';

const etag = (revision: number) => '"qa-v1-' + String(revision + 1).repeat(64) + '"';

test.describe('T050 Quiz Runner', () => {
  test('restores three question types after browser reload and saves a blur-flushed answer', async ({ page }) => {
    let revision = 0;
    let savedAnswer = '';
    let puts = 0;
    await page.route('/api/v1/quiz-attempts/attempt-123', async route => {
      await route.fulfill({
        status: 200,
        json: {
          id: 'attempt-123', noteDate: '2026-10-11', status: 'IN_PROGRESS', result: null,
          savedAnswerCount: revision ? 1 : 0, snapshotRevision: 1, submissionRevision: 0,
          questions: [
            { id: 'q1', type: 'MCQ', wordFormId: 'wf1', promptEn: 'MCQ Prompt',
              options: [{ id: 'o1', textEn: 'Option one' }, { id: 'o2', textEn: 'Option two' }] },
            { id: 'q2', type: 'CLOZE', wordFormId: 'wf2', promptEn: 'CLOZE Prompt',
              answerPolicyVersion: 'cloze-answer-v1' },
            { id: 'q3', type: 'WRITING', wordFormId: 'wf3', promptEn: 'WRITING Prompt',
              targetLemma: 'apple', rubricVersion: 'writing-rubric-v1',
              rubric: { descriptors: [0, 1, 2, 3, 4].map(score => ({ score, textVi: 'Mức ' + score })) } },
            { id: 'q4', type: 'MCQ', wordFormId: 'wf4', promptEn: 'Second MCQ Prompt',
              options: [{ id: 'o3', textEn: 'Option three' }, { id: 'o4', textEn: 'Option four' }] },
            { id: 'q5', type: 'CLOZE', wordFormId: 'wf5', promptEn: 'Second CLOZE Prompt',
              answerPolicyVersion: 'cloze-answer-v1' },
          ],
          answerPreconditions: ['q1', 'q2', 'q3', 'q4', 'q5'].map(questionId => ({
            questionId, draftRevision: questionId === 'q2' ? revision : 0,
            etag: etag(questionId === 'q2' ? revision : 0),
          })),
          answers: revision ? [{
            attemptId: 'attempt-123', questionId: 'q2', answer: savedAnswer, selfScore: null,
            draftRevision: revision, savedAt: '2026-10-11T00:00:00Z',
            operationId: 'operation-1', state: 'DRAFT',
          }] : [],
        },
      });
    });

    await page.route('/api/v1/quiz-attempts/attempt-123/answers/q2', async route => {
      if (route.request().method() !== 'PUT') return route.fallback();
      const body = route.request().postDataJSON() as { answer: string; draftRevision: number; selfScore: number | null };
      if (body.draftRevision !== revision || route.request().headers()['if-match'] !== etag(revision)) {
        await route.fulfill({
          status: 409,
          json: { error: { code: 'REVISION_CONFLICT', message: 'Stale revision', requestId: 'req-stale' } },
        });
        return;
      }
      puts++;
      savedAnswer = body.answer;
      revision++;
      await route.fulfill({
        status: 200,
        headers: { ETag: etag(revision) },
        json: {
          attemptId: 'attempt-123', questionId: 'q2', answer: savedAnswer, selfScore: body.selfScore,
          draftRevision: revision, operationId: 'operation-' + revision,
          savedAt: '2026-10-11T00:00:00Z', state: 'DRAFT',
        },
      });
    });

    await page.goto('/quiz/attempt-123');
    await expect(page.getByRole('heading', { name: 'Làm bài kiểm tra' }).first()).toBeVisible();
    await expect(page.getByText('MCQ Prompt', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Điểm 4')).toBeVisible();
    const input = page.getByLabel('Câu trả lời:', { exact: true }).first();
    await input.fill('persistent answer');
    await input.blur();
    await expect(page.getByText('Đã lưu', { exact: true })).toBeVisible();
    expect(puts).toBe(1);

    await page.reload();
    await expect(page.getByLabel('Câu trả lời:', { exact: true }).first()).toHaveValue('persistent answer');
    expect(puts).toBe(1);
  });

  test('a failed initial local GET shows retry instead of a fabricated empty quiz', async ({ page }) => {
    await page.route('/api/v1/quiz-attempts/attempt-offline', async route => {
      await route.abort('failed');
    });
    await page.goto('/quiz/attempt-offline');
    await expect(page.getByRole('alert')).toContainText('Không thể tải bài kiểm tra');
    await expect(page.getByText('CLOZE Prompt')).toHaveCount(0);
    await page.route('/api/v1/quiz-attempts/attempt-offline', async route => {
      await route.fulfill({
        status: 200,
        json: {
          id: 'attempt-offline', noteDate: '2026-10-11', status: 'IN_PROGRESS',
          result: null, savedAnswerCount: 0, snapshotRevision: 1, submissionRevision: 0,
          questions: [{ id: 'q1', wordFormId: 'wf1', type: 'CLOZE',
            promptEn: 'CLOZE Prompt', answerPolicyVersion: 'cloze-answer-v1' }],
          answerPreconditions: [{ questionId: 'q1', draftRevision: 0, etag: etag(0) }],
          answers: [],
        },
      });
    });
    await page.getByRole('button', { name: 'Thử lại' }).click();
    await expect(page.getByText('CLOZE Prompt')).toBeVisible();
  });
});
