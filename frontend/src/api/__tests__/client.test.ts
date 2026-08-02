import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('apiRequest', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends request with credentials include', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ data: 'ok' })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');
    await apiRequest('/test');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/test'),
      expect.objectContaining({
        credentials: 'include',
      }),
    );
    // No Content-Type when no body
    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Content-Type']).toBeUndefined();
  });

  it('sets Content-Type when body is provided', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ data: 'ok' })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');
    await apiRequest('/test', { method: 'POST', body: JSON.stringify({ foo: 'bar' }) });

    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('redirects to login on 401 response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: () => Promise.resolve(JSON.stringify({ detail: 'Unauthorized' })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const originalHref = window.location.href;
    Object.defineProperty(window, 'location', {
      value: { href: originalHref },
      writable: true,
    });

    const { apiRequest } = await import('../client');

    await expect(apiRequest('/protected')).rejects.toThrow('Unauthorized');
  });

  it('throws error on failed request with detail message', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: () => Promise.resolve(JSON.stringify({ detail: '请求参数错误' })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');

    await expect(apiRequest('/bad-request')).rejects.toThrow('请求参数错误');
  });

  it('throws fallback error when no detail in response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve(JSON.stringify({})),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');

    await expect(apiRequest('/error')).rejects.toThrow('服务器内部错误，请稍后重试');
  });
});
