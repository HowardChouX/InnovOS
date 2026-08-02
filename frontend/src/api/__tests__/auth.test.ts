import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('authApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('login posts FormData (OAuth2 form) to /api/auth/jwt/login', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      text: () => Promise.resolve(''),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { authApi } = await import('../auth');
    await authApi.login('user@example.com', 'pass1234');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/jwt/login'),
      expect.objectContaining({ method: 'POST' }),
    );
    const body = mockFetch.mock.calls[0][1].body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get('username')).toBe('user@example.com');
    expect(body.get('password')).toBe('pass1234');
  });

  it('register posts email + password + optional fields to /api/auth/register', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: () => Promise.resolve(JSON.stringify({ id: 1, email: 'a@b.com', is_superuser: false })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { authApi } = await import('../auth');
    const u = await authApi.register({
      email: 'a@b.com',
      password: 'pass1234',
      phone: '13800138000',
    });
    expect(u.email).toBe('a@b.com');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/register'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'a@b.com',
          password: 'pass1234',
          phone: '13800138000',
        }),
      }),
    );
  });

  it('me calls /api/users/me', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ id: 1, email: 'a@b.com' })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { authApi } = await import('../auth');
    await authApi.me();
    expect(mockFetch.mock.calls[0][0]).toContain('/api/users/me');
  });
});
