// FastAPI Users 认证 API 客户端。
//
// 端点契约（见 backend/app/main.py 第 242-261 行）：
// - POST /api/auth/register              {email, password, username?, phone?} → UserRead
// - POST /api/auth/jwt/login             {username:email, password} → 204 + Set-Cookie
// - POST /api/auth/jwt/logout            → 204
// - POST /api/auth/forgot-password       {email} → 202
// - POST /api/auth/reset-password        {token, password} → 200
// - POST /api/auth/request-verify-token  {email} → 202
// - POST /api/auth/verify                {token} → 200
//
// UserRead 形状：{id, email, username?, phone?, role, isActive, isSuperuser, isVerified}
//
// 注意：FastAPI Users 的登录字段统一命名为 "username"（任意标识符；InnovOS 用 email）。
import { apiRequest } from './client';

export interface AuthUser {
  id: number;
  email: string;
  username?: string | null;
  phone?: string | null;
  role: string;
  // FastAPI Users 默认 Pydantic 是 snake_case 而非驼峰
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export const authApi = {
  /** 注册：email + password + 可选 username/phone */
  register(input: {
    email: string;
    password: string;
    username?: string;
    phone?: string;
  }): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  /** 登录：FastAPI Users 端点用 OAuth2PasswordRequestForm（form-urlencoded，不是 JSON） */
  login(email: string, password: string): Promise<void> {
    const form = new FormData();
    form.append('username', email);
    form.append('password', password);
    return apiRequest<void>('/api/auth/jwt/login', {
      method: 'POST',
      body: form,
    });
  },

  /** 登出 */
  logout(): Promise<void> {
    return apiRequest<void>('/api/auth/jwt/logout', { method: 'POST' });
  },

  /** 当前用户（FastAPI Users users router 提供） */
  me(): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/users/me');
  },

  /** 忘记密码 — 触发邮件发送，返回 202（防探测） */
  forgotPassword(email: string): Promise<void> {
    return apiRequest<void>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 重置密码 — 邮件里的 token + 新密码 */
  resetPassword(token: string, password: string): Promise<void> {
    return apiRequest<void>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    });
  },

  /** 请求邮箱验证邮件 */
  requestVerifyToken(email: string): Promise<void> {
    return apiRequest<void>('/api/auth/request-verify-token', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 用 token 完成邮箱验证 */
  verify(token: string): Promise<void> {
    return apiRequest<void>('/api/auth/verify', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  },

  /** 请求邮箱验证码（6 位 OTP） */
  requestEmailOtp(email: string): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/email-verifications/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 重发邮箱验证码 */
  resendEmailOtp(email: string): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/email-verifications/resend', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  /** 验证邮箱验证码 */
  verifyEmailOtp(email: string, code: string): Promise<{ verified: boolean; already?: boolean }> {
    return apiRequest('/api/auth/email-verifications/verify', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    });
  },
};
