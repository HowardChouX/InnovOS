/// <reference types="vite/client" />

// In production (nginx reverse proxy), API is same origin → empty string.
// In development, Vite proxy or explicit URL.
const BASE = import.meta.env.VITE_API_URL ?? '';

function buildHeaders(options?: RequestInit): HeadersInit {
  const headers: Record<string, string> = {};
  // Only set Content-Type for JSON string bodies; allow FormData to set its own boundary
  if (options?.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

/**
 * 从后端错误响应中提取人类可读的消息。
 *
 * 后端有两种错误格式：
 * 1. FastAPI 标准：{"detail": "string"} 或 {"detail": [{loc, msg, type}]}
 * 2. 自定义 SMS 异常：{"code": "SMS_xxx", "message": "中文消息", "detail": {retry_after: N}}
 */
// FastAPI Users 内置错误码 → 中文映射
const ERROR_CODE_MAP: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: '手机号或密码错误',
  LOGIN_USER_NOT_VERIFIED: '账号未验证，请先完成手机验证',
};

function extractErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;

    // 自定义异常格式：优先取 message 字段（中文用户可见消息）
    if (typeof obj.message === 'string' && obj.message) {
      return obj.message;
    }

    // FastAPI 标准格式（detail 可能是错误码字符串，如 LOGIN_BAD_CREDENTIALS）
    const detail = obj.detail;
    if (typeof detail === 'string' && detail) {
      return ERROR_CODE_MAP[detail] ?? detail;
    }

    // FastAPI 验证错误：detail 是数组 [{loc, msg, type}]
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      if (typeof first?.msg === 'string') return first.msg;
    }
  }

  // 按状态码给出有意义的兜底消息
  const statusMessages: Record<number, string> = {
    400: '请求参数错误',
    403: '没有操作权限',
    404: '资源不存在',
    429: '操作过于频繁，请稍后再试',
    500: '服务器内部错误，请稍后重试',
    502: '服务暂时不可用',
    503: '服务暂时不可用，请稍后重试',
  };
  return statusMessages[status] ?? `请求失败 (${status})`;
}

export async function apiRequest<T>(
  path: string,
  options?: RequestInit & { signal?: AbortSignal },
  /** Set to true to skip JSON parsing (for non-JSON responses) */
  rawResponse?: boolean,
): Promise<T> {
  // httpOnly cookie is sent automatically by the browser (credentials: 'include').
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...buildHeaders(options),
      ...(options?.headers as Record<string, string> | undefined),
    },
  });

  // Handle empty responses or raw response
  if (rawResponse || res.status === 204) {
    return {} as T;
  }

  const text = await res.text();

  let data: T;
  try {
    data = text ? JSON.parse(text) : ({} as T);
  } catch {
    throw new Error(text ? `服务器返回了非 JSON 响应: ${text.slice(0, 80)}` : '服务器无响应');
  }

  if (!res.ok) {
    if (res.status === 401) {
      const { useAuthStore } = await import('../store/useAuthStore');
      const store = useAuthStore.getState();
      // Only clear state if user is still logged in (avoid redundant clears on login page)
      if (store.user) {
        store.logout?.();
      }
    }
    throw new Error(extractErrorMessage(data, res.status));
  }
  return data;
}
