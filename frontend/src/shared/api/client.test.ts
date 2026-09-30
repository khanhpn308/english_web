import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient, ApiError, NetworkError, getETag } from './client';

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

  it('maps valid ErrorResponse to typed error union', async () => {
    const errorBody = {
      error: {
        code: 'CONFLICT',
        message: 'Conflict occurred',
        requestId: 'req_123',
        details: {
          kind: 'CONFLICT',
          expectedRevision: 1,
          currentRevision: 2
        }
      }
    };

    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(errorBody), {
        status: 409,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    try {
      await apiClient('/api/v1/some-endpoint', { method: 'POST' });
      expect.fail('Should have thrown ApiError');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.code).toBe('CONFLICT');
      expect(apiError.requestId).toBe('req_123');
      expect(apiError.details?.kind).toBe('CONFLICT');
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

  it('treats mutation unknown outcome as NetworkError, not success', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    try {
      await apiClient('/api/v1/operations', { method: 'POST', body: JSON.stringify({ key: 'value' }) });
      expect.fail('Should have thrown NetworkError');
    } catch (error) {
      expect(error).toBeInstanceOf(NetworkError);
    }
  });
});
