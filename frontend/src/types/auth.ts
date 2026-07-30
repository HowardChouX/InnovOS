// FastAPI Users 认证领域类型。
//
// UserRead 形状：{id, email, username?, phone?, role, isActive, isSuperuser, isVerified}
// 注意：FastAPI Users 默认 Pydantic 是 snake_case 而非驼峰。

export interface AuthUser {
  id: number;
  email: string;
  username?: string | null;
  phone?: string | null;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}
