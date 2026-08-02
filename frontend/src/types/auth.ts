// FastAPI Users 认证领域类型。
//
// UserRead 形状：{id, email?, phone, username?, isActive, isSuperuser, isVerified}
// 注意：FastAPI Users 默认 Pydantic 是 snake_case 而非驼峰。

export interface AuthUser {
  id: number;
  email?: string | null;
  username?: string | null;
  phone: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at?: string | null;
}
