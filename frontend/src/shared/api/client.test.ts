import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient, ApiError, NetworkError, MutationUnknownError, getETag } from './client';

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
      expect((mutError as Record<string, unknown>).body).toBeUndefined();
    }
  });
});
