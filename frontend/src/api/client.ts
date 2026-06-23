/// <reference types="vite/client" />

// In production (nginx reverse proxy), API is same origin → empty string.
// In development, Vite proxy or explicit URL.
const BASE = import.meta.env.VITE_API_URL ?? '';

function buildHeaders(options?: RequestInit): HeadersInit {
  const headers: Record<string, string> = {};
  // Only set Content-Type when there's a body to send
  if (options?.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  // httpOnly cookie is sent automatically by the browser (credentials: 'include').
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    body: options?.body ?? null,
    credentials: 'include',
    headers: {
      ...buildHeaders(options),
      ...(options?.headers as Record<string, string> | undefined),
    },
  });
  // Handle empty responses (204, etc.)
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/login';
    }
    throw new Error(data.detail || '请求失败');
  }
  return data;
}
