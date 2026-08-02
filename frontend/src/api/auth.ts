// FastAPI Users 认证 API 客户端（短信验证码版）。
//
// 端点契约（见 backend/app/main.py 路由挂载）：
// - POST /api/auth/register              {phone, password, email?, username?} → UserRead
// - POST /api/auth/jwt/login             form(username=phone, password) → 204 + Set-Cookie
// - POST /api/auth/jwt/logout            → 204
// - POST /api/auth/login/code            {phone, code} → AuthUser（验证码登录）
// - POST /api/auth/sms-verifications/send   {phone, purpose} → {expires_in, next_resend_in}
// - POST /api/auth/sms-verifications/verify {phone, code, purpose} → {verified, already?}
// - POST /api/auth/password-reset/send-code {phone} → {expires_in, next_resend_in}
// - POST /api/auth/password-reset/verify    {phone, code, new_password} → {reset}
//
// UserRead 形状：{id, email?, phone, username?, isActive, isSuperuser, isVerified}
//
// 注意：FastAPI Users 的登录字段统一命名为 "username"（任意标识符；InnovOS 用 phone）。
import { apiRequest } from './client';
import type { AuthUser } from '../types/auth';

export const authApi = {
  /** 注册：phone 必填，email 可选（仅通知用） */
  register(input: {
    phone: string;
    password: string;
    email?: string;
    username?: string;
  }): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  /** 登录：手机号 + 密码（FastAPI Users 用 OAuth2PasswordRequestForm，form-urlencoded） */
  login(phone: string, password: string): Promise<void> {
    const form = new FormData();
    form.append('username', phone);
    form.append('password', password);
    return apiRequest<void>('/api/auth/jwt/login', {
      method: 'POST',
      body: form,
    });
  },

  /** 登录：手机号 + 短信验证码 */
  loginWithCode(phone: string, code: string): Promise<AuthUser> {
    return apiRequest<AuthUser>('/api/auth/login/code', {
      method: 'POST',
      body: JSON.stringify({ phone, code }),
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

  /** 发送短信验证码（注册/登录） */
  sendSmsCode(
    phone: string,
    purpose: 'register' | 'login' = 'register',
  ): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/sms-verifications/send', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose }),
    });
  },

  /** 核验短信验证码（注册场景：通过后激活账号并自动登录，返回 user + Set-Cookie） */
  verifySmsCode(
    phone: string,
    code: string,
    purpose: 'register' | 'login' = 'register',
  ): Promise<{ verified: boolean; already?: boolean; user?: AuthUser }> {
    return apiRequest('/api/auth/sms-verifications/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, purpose }),
    });
  },

  /** 密码重置：发送短信验证码 */
  requestPasswordResetSms(phone: string): Promise<{ expires_in: number; next_resend_in: number }> {
    return apiRequest('/api/auth/password-reset/send-code', {
      method: 'POST',
      body: JSON.stringify({ phone }),
    });
  },

  /** 密码重置：验证码 + 新密码 */
  resetPasswordWithSms(
    phone: string,
    code: string,
    newPassword: string,
  ): Promise<{ reset: boolean }> {
    return apiRequest('/api/auth/password-reset/verify', {
      method: 'POST',
      body: JSON.stringify({ phone, code, new_password: newPassword }),
    });
  },
};
