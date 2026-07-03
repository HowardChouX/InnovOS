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
      useAuthStore.getState().logout?.();
      setTimeout(() => {
        window.location.href = '/login';
      }, 100);
    }
    throw new Error((data as { detail?: string }).detail || '请求失败');
  }
  return data;
}
