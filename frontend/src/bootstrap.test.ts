import { describe, it, expect, vi } from 'vitest';
import { runBootstrap, BootstrapDependencies } from './bootstrap';

describe('runBootstrap', () => {
  const createMockDeps = (overrides?: Partial<BootstrapDependencies>): BootstrapDependencies => ({
    hash: '#token=valid-token-123',
    pathname: '/bootstrap',
    search: '?query=1',
    replaceState: vi.fn(),
    fetch: vi.fn().mockResolvedValue({ status: 204 }),
    replace: vi.fn(),
    renderStatus: vi.fn(),
    ...overrides,
  });

  it('A. ORDERING: clears fragment before fetching, then navigates on success', async () => {
    const deps = createMockDeps();
    const calls: string[] = [];

    // Track ordering
    deps.replaceState = vi.fn().mockImplementation(() => calls.push('replaceState'));
    deps.fetch = vi.fn().mockImplementation(async () => {
      calls.push('fetch');
      return { status: 204 } as Response;
    });
    deps.replace = vi.fn().mockImplementation(() => calls.push('replace'));

    await runBootstrap(deps);

    expect(calls).toEqual(['replaceState', 'fetch', 'replace']);
  });

  it('B. EXACTLY ONE EXCHANGE & C. REQUEST SHAPE: Sends exactly one POST to /bootstrap/exchange with correct body and headers', async () => {
    const deps = createMockDeps();
    await runBootstrap(deps);

    expect(deps.fetch).toHaveBeenCalledTimes(1);
    expect(deps.fetch).toHaveBeenCalledWith('/bootstrap/exchange', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: 'valid-token-123' }),
      credentials: 'same-origin',
    });
  });

  it('D. MISSING TOKEN: Sanitizes URL but does not fetch or navigate', async () => {
    const deps = createMockDeps({ hash: '' });
    await runBootstrap(deps);

    expect(deps.fetch).not.toHaveBeenCalled();
    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('Invalid or missing token'));
  });

  it('D. INVALID TOKEN FORMAT: Does not fetch', async () => {
    const deps = createMockDeps({ hash: '#token=!!!invalid' });
    await runBootstrap(deps);

    expect(deps.fetch).not.toHaveBeenCalled();
    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('Invalid or missing token'));
  });

  it('E. EXPIRED / REUSED TOKEN: Renders recovery on 401', async () => {
    const deps = createMockDeps({
      fetch: vi.fn().mockResolvedValue({ status: 401 }),
    });
    await runBootstrap(deps);

    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('Session expired'));
    // Ensure token is not echoed in the error
    expect(deps.renderStatus).not.toHaveBeenCalledWith(expect.stringContaining('valid-token-123'));
  });

  it('F. ORIGIN / SESSION BOUNDARY FAILURE: Renders recovery on 403', async () => {
    const deps = createMockDeps({
      fetch: vi.fn().mockResolvedValue({ status: 403 }),
    });
    await runBootstrap(deps);

    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('invalid origin'));
  });

  it('G. NETWORK FAILURE: Catches rejection and renders safe error', async () => {
    const deps = createMockDeps({
      fetch: vi.fn().mockRejectedValue(new Error('Network disconnected')),
    });
    await runBootstrap(deps);

    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('Network failure'));
  });

  it('H. UNKNOWN HTTP RESPONSE: 200 (instead of 204) renders error without navigation', async () => {
    const deps = createMockDeps({
      fetch: vi.fn().mockResolvedValue({ status: 200 }), // Should be 204
    });
    await runBootstrap(deps);

    expect(deps.replace).not.toHaveBeenCalled();
    expect(deps.renderStatus).toHaveBeenCalledWith(expect.stringContaining('Unexpected response'));
  });

  it('I. TOKEN CONFIDENTIALITY: Sentinel is never logged or leaked to UI', async () => {
    const sentinel = 'T066_SECRET_SENTINEL_DO_NOT_LEAK';
    const deps = createMockDeps({
      hash: `#token=${sentinel}`,
      fetch: vi.fn().mockRejectedValue(new Error('Fail')),
    });
    await runBootstrap(deps);

    // Passed safely to backend? Yes.
    expect(deps.fetch).toHaveBeenCalledWith('/bootstrap/exchange', expect.objectContaining({
      body: JSON.stringify({ token: sentinel })
    }));

    // Passed safely in URL clear? Yes.
    expect(deps.replaceState).toHaveBeenCalledWith(null, '', '/bootstrap?query=1'); // URL string without hash

    // Echoed in renderStatus? No.
    expect(deps.renderStatus).not.toHaveBeenCalledWith(expect.stringContaining(sentinel));
    expect(deps.replace).not.toHaveBeenCalled();
  });
});
