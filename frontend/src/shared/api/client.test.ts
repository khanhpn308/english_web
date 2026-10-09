import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient, ApiError, NetworkError, MutationUnknownError, getETag } from './client';
import type { components } from './generated';

describe('apiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('maps valid JSON success to typed result and handles same-origin credentials', async () => {
    const mockData = { status: 'OK' };
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'ETag': 'W/"opaque-etag-123"'
        }
      })
    );

    const result = await apiClient('/api/v1/health');
    
    expect(result).toEqual(mockData);
    expect(getETag(result)).toBe('W/"opaque-etag-123"');
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({
      credentials: 'same-origin'
    }));
  });

  it('safely handles JSON null + ETag without crashing', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('null', {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'ETag': 'W/"opaque-etag-456"'
        }
      })
    );

    const result = await apiClient('/api/v1/health');
    expect(result).toBeNull();
    expect(getETag(result)).toBeUndefined();
  });

  it('maps valid ErrorResponse to typed error union', async () => {
    const errorBody = {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        requestId: 'req_123',
        details: {
          kind: 'FIELD_ERRORS',
          fields: [{ field: 'body', reason: 'invalid' }]
        }
      }
    };

    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(errorBody), {
        status: 422,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    try {
      await apiClient('/api/v1/some-endpoint', { method: 'POST' });
      expect.fail('Should have thrown ApiError');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.code).toBe('VALIDATION_ERROR');
      expect(apiError.requestId).toBe('req_123');
      expect(apiError.details?.kind).toBe('FIELD_ERRORS');
    }
  });

  it('preserves typed conflict details for source recovery', async () => {
    const body: components['schemas']['ErrorResponse'] = {
      error: {
        code: 'REVISION_CONFLICT', message: 'Source revision changed', requestId: 'req_fixture',
        details: {
          kind: 'CONFLICT', expectedRevision: 1, currentRevision: 2,
          resourceType: 'SOURCE', resourceId: 'src_fixture',
        },
      },
    };
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), {
      status: 409, headers: { 'Content-Type': 'application/json' },
    }));
    try {
      await apiClient('/api/v1/word-forms', { method: 'POST' });
      expect.fail('Should have thrown ApiError');
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      const details = error.details;
      if (details?.kind !== 'CONFLICT') throw new Error('Expected source conflict');
      const expectedRevision: number = details.expectedRevision;
      const currentRevision: number = details.currentRevision;
      const resourceId: string = details.resourceId;
      expect([expectedRevision, currentRevision, resourceId]).toEqual([1, 2, 'src_fixture']);
      expect(details).toEqual(body.error.details);
    }
  });

  it('preserves typed restore guidance for an unavailable quiz snapshot', async () => {
    const body: components['schemas']['ErrorResponse'] = {
      error: {
        code: 'QUIZ_RESTORE_REQUIRED', message: 'Quiz snapshot requires restoration',
        requestId: 'req_fixture', details: {
          kind: 'RESTORE', attemptId: 'attempt_fixture', guidanceCode: 'QUIZ_RESTORE_REQUIRED',
        },
      },
    };
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), {
      status: 409, headers: { 'Content-Type': 'application/json' },
    }));
    try {
      await apiClient('/api/v1/quiz-attempts/attempt_fixture');
      expect.fail('Should have thrown ApiError');
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      const details = error.details;
      if (details?.kind !== 'RESTORE') throw new Error('Expected quiz restore guidance');
      const attemptId: string = details.attemptId;
      const guidanceCode: 'QUIZ_RESTORE_REQUIRED' = details.guidanceCode;
      expect([attemptId, guidanceCode]).toEqual(['attempt_fixture', 'QUIZ_RESTORE_REQUIRED']);
      expect(details).toEqual(body.error.details);
    }
  });

  it('keeps generated request constraints usable without handwritten DTOs', () => {
    const newSave: components['schemas']['SaveWordFormsRequest'] = {
      lookupId: 'lookup_fixture', noteDate: '2026-10-09',
    };
    const existingSave: components['schemas']['SaveWordFormsRequest'] = {
      ...newSave, sourceId: 'src_fixture', sourceRevision: 1,
    };
    const edit: components['schemas']['PatchWordFormRequest'] = {
      sourceId: 'src_fixture', sourceRevision: 1, ipaUs: null, cambridgeUrl: null,
    };
    const flashcard: components['schemas']['ReviewRequest'] = {
      source: 'FLASHCARD', rating: 'GOOD', attemptId: null, questionId: null,
    };
    const quiz: components['schemas']['ReviewRequest'] = {
      source: 'QUIZ', rating: 'AGAIN', attemptId: 'attempt_fixture', questionId: 'q_fixture',
    };
    // These assignments fail typecheck if generation again permits invalid requests.
    const partialSaveAccepted: {
      lookupId: string; noteDate: string; sourceId: string;
    } extends components['schemas']['SaveWordFormsRequest'] ? true : false = false;
    const nullSaveAccepted: {
      lookupId: string; noteDate: string; sourceId: null; sourceRevision: null;
    } extends components['schemas']['SaveWordFormsRequest'] ? true : false = false;
    const emptyEditAccepted: {
      sourceId: string; sourceRevision: number;
    } extends components['schemas']['PatchWordFormRequest'] ? true : false = false;
    const nullLearningAccepted: {
      sourceId: string; sourceRevision: number; meaningsEn: null; ipaUs: null;
    } extends components['schemas']['PatchWordFormRequest'] ? true : false = false;
    const missingQuizProvenanceAccepted: {
      source: 'QUIZ'; rating: 'GOOD';
    } extends components['schemas']['ReviewRequest'] ? true : false = false;
    const flashcardProvenanceAccepted: {
      source: 'FLASHCARD'; rating: 'GOOD'; attemptId: string;
    } extends components['schemas']['ReviewRequest'] ? true : false = false;
    expect([newSave, existingSave, edit, flashcard, quiz]).toHaveLength(5);
    expect([
      partialSaveAccepted, nullSaveAccepted, emptyEditAccepted, nullLearningAccepted,
      missingQuizProvenanceAccepted, flashcardProvenanceAccepted,
    ]).toEqual([false, false, false, false, false, false]);
  });

  it('narrows the generated QuizAttempt result by status', async () => {
    const inProgress: components['schemas']['QuizAttempt'] = {
      id: 'attempt_fixture', noteDate: '2026-10-09', status: 'IN_PROGRESS',
      questions: Array.from({ length: 5 }, (_, index) => ({
        id: `q_${index}`, type: 'MCQ' as const, wordFormId: `wf_${index}`,
        promptEn: 'Choose the synthetic word.', options: [{ id: 'option_a', textEn: 'synthetic' }],
      })),
      answers: [], savedAnswerCount: 0, snapshotRevision: 1, submissionRevision: 0, result: null,
    };
    const result: components['schemas']['QuizResult'] = {
      attemptId: 'attempt_fixture', status: 'SUBMITTED', submissionRevision: 0,
      objectiveScores: {
        mcq: { total: 5, attempted: 0, correct: 0, accuracy: null },
        cloze: { total: 0, attempted: 0, correct: 0, accuracy: null },
      },
      writingSelfScores: [],
      questionResults: inProgress.questions.map(question => ({
        questionId: question.id, type: 'MCQ', outcome: 'BLANK', isCorrect: false,
        rating: 'AGAIN', correctOptionId: 'option_a', explanationVi: 'Synthetic explanation.',
      })),
      reviewHandoffs: inProgress.questions.map(question => ({
        wordFormId: question.wordFormId, cardId: null, rating: 'AGAIN', reviewEventId: null,
        status: 'SKIPPED_INACTIVE',
      })),
      submittedAt: '2026-10-09T00:00:00Z',
    };
    const submitted: components['schemas']['QuizAttempt'] = {
      ...inProgress, status: 'SUBMITTED', result,
    };
    function resultCount(attempt: components['schemas']['QuizAttempt']): number | null {
      if (attempt.status === 'IN_PROGRESS') {
        const pendingResult: null = attempt.result;
        return pendingResult;
      }
      const terminalResult: components['schemas']['QuizResult'] = attempt.result;
      return terminalResult.questionResults.length;
    }
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(inProgress), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(submitted), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }));
    const pending = await apiClient<components['schemas']['QuizAttempt']>(
      '/api/v1/quiz-attempts/attempt_fixture',
    );
    const terminal = await apiClient<components['schemas']['QuizAttempt']>(
      '/api/v1/quiz-attempts/attempt_fixture',
    );
    expect(resultCount(pending)).toBeNull();
    expect(resultCount(terminal)).toBe(5);
  });

  it('maps non-JSON 500 to typed client failure without crashing', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('<html><body>500 Internal Server Error</body></html>', {
        status: 500,
        headers: { 'Content-Type': 'text/html' }
      })
    );

    try {
      await apiClient('/api/v1/health');
      expect.fail('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.code).toBe('INTERNAL_ERROR');
      expect(apiError.requestId).toBe('req_unknown');
    }
  });

  it('handles malformed error body safely', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('{ "invalid_json": true ', {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'x-request-id': 'req_malformed' }
      })
    );

    try {
      await apiClient('/api/v1/health');
      expect.fail('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.code).toBe('MALFORMED_JSON');
      expect(apiError.requestId).toBe('req_malformed');
    }
  });

  it('aborts read request and distinguishes from success', async () => {
    const controller = new AbortController();
    vi.spyOn(global, 'fetch').mockRejectedValue(new DOMException('Aborted', 'AbortError'));

    try {
      await apiClient('/api/v1/health', { signal: controller.signal });
      expect.fail('Should have thrown AbortError');
    } catch (error) {
      expect(error).toBeInstanceOf(DOMException);
      expect((error as DOMException).name).toBe('AbortError');
    }
  });

  it('treats GET network outcome as regular NetworkError without reconciliation context', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    try {
      await apiClient('/api/v1/health');
      expect.fail('Should have thrown NetworkError');
    } catch (error) {
      expect(error).toBeInstanceOf(NetworkError);
      expect(error).not.toBeInstanceOf(MutationUnknownError);
      const netError = error as NetworkError;
      expect(netError.method).toBe('GET');
      expect(netError.url).toBe('/api/v1/health');
    }
  });

  it('treats mutation unknown outcome as MutationUnknownError and retains safe intent for replay (Path B)', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    try {
      // Path B: operationId is UNKNOWN because the HTTP response was lost before we could read it.
      // We must preserve the Idempotency-Key so the caller can replay the EXACT SAME mutation intent.
      // Idempotency-Key CANNOT be used to GET /operations/{id}.
      await apiClient('/api/v1/some-resource', { 
        method: 'POST', 
        headers: { 'Idempotency-Key': 'idemp_abc' },
        body: JSON.stringify({ key: 'secret_value' }) 
      });
      expect.fail('Should have thrown MutationUnknownError');
    } catch (error) {
      expect(error).toBeInstanceOf(MutationUnknownError);
      const mutError = error as MutationUnknownError;
      expect(mutError.method).toBe('POST');
      expect(mutError.url).toBe('/api/v1/some-resource');
      
      // 1. Idempotency-Key is preserved exactly.
      expect(mutError.idempotencyKey).toBe('idemp_abc');
      
      // 2. operationId is undefined (never received, not synthesized, not faked).
      expect(mutError.operationId).toBeUndefined();
      
      // 3. Raw request body is NOT copied. The caller already owns its draft state.
      expect((mutError as unknown as Record<string, unknown>).body).toBeUndefined();
    }
  });
});
