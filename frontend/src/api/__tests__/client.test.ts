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

  it('extracts reason when detail is a structured object', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: () =>
        Promise.resolve(
          JSON.stringify({
            detail: { code: 'REGISTER_INVALID_PASSWORD', reason: '密码至少 8 位' },
          }),
        ),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');

    await expect(apiRequest('/register')).rejects.toThrow('密码至少 8 位');
  });

  it('prefers top-level reason and carries code on ApiError', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: () =>
        Promise.resolve(
          JSON.stringify({
            code: 'LOGIN_USER_NOT_VERIFIED',
            reason: '账号未验证，请先完成手机验证',
          }),
        ),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest, ApiError } = await import('../client');

    try {
      await apiRequest('/login');
      expect.unreachable('should have thrown');
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as InstanceType<typeof ApiError>).code).toBe('LOGIN_USER_NOT_VERIFIED');
      expect((e as Error).message).toBe('账号未验证，请先完成手机验证');
    }
  });

  it('extracts first msg from 422 validation array', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: () =>
        Promise.resolve(
          JSON.stringify({
            detail: [
              {
                loc: ['body', 'phone'],
                msg: '手机号格式不正确（11 位数字，1 开头）',
                type: 'string_pattern_mismatch',
              },
            ],
          }),
        ),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { apiRequest } = await import('../client');

    await expect(apiRequest('/register')).rejects.toThrow('手机号格式不正确（11 位数字，1 开头）');
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
