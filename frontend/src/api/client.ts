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
 * 后端统一错误契约：{code, reason}，reason 为用户可见中文（唯一真源在后端）。
 * 前端只负责提取 reason 显示，不做码表映射；code 供页面做分支判断（如未验证跳转）。
 *
 * 兼容的历史格式：
 * - SMS 异常：顶层 {code, message, reason}
 * - FastAPI 422：detail 为数组 [{loc, msg, type}]（msg 已由后端翻译成中文）
 * - 旧版 detail 字符串：仅作兜底
 */
export class ApiError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

function extractError(data: unknown, status: number): { message: string; code?: string } {
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    const code = typeof obj.code === 'string' ? obj.code : undefined;

    // 统一契约：顶层 reason（中文用户可见消息）
    if (typeof obj.reason === 'string' && obj.reason) {
      return { message: obj.reason, code };
    }
    // SMS 异常：message 字段
    if (typeof obj.message === 'string' && obj.message) {
      return { message: obj.message, code };
    }

    const detail = obj.detail;
    // 业务错误：detail 为对象 {code, reason}
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const d = detail as Record<string, unknown>;
      if (typeof d.reason === 'string' && d.reason) {
        return { message: d.reason, code: typeof d.code === 'string' ? d.code : code };
      }
    }
    // FastAPI 422：detail 为数组 [{loc, msg, type}]（msg 已中文化）
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      if (typeof first?.msg === 'string') return { message: first.msg, code };
    }
    // 旧版兜底：detail 字符串
    if (typeof detail === 'string' && detail) {
      return { message: detail, code };
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
  return { message: statusMessages[status] ?? `请求失败 (${status})` };
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
    const { message, code } = extractError(data, res.status);
    throw new ApiError(message, code);
  }
  return data;
}
