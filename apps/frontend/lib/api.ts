/**
 * Auto-detects API URL based on environment and context.
 * - In browser: uses relative URLs (same origin) OR explicit NEXT_PUBLIC_API_URL
 * - For cloudflare tunnels: requires explicit NEXT_PUBLIC_API_URL pointing to tunneled backend
 */
export function getApiUrl(): string {
  // If explicitly set (for cloudflare tunnels, etc)
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  // In browser with same-origin API, use relative URL
  if (typeof window !== 'undefined') {
    return ''; // Empty = relative URL (same origin)
  }

  // Server-side fallback for SSR
  return 'http://localhost:8000';
}

import { getLegacyToken } from './auth-cookie';

/**
 * Fetch wrapper that auto-selects API URL and includes auth credentials.
 *
 * Auth strategy (S0-04):
 * - Prefers the HttpOnly `lilian_auth_token` cookie, sent automatically by
 *   the browser on same-origin requests.
 * - Falls back to a legacy `Authorization: Bearer <jwt>` header built from
 *   localStorage so older call-sites keep working during the migration.
 * - Uses `credentials: 'include'` so cross-origin requests still carry the
 *   cookie once the backend CORS config is tightened.
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const baseUrl = getApiUrl();
  const url = baseUrl ? `${baseUrl}${endpoint}` : endpoint;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };

  // Attach Authorization only as a fallback when no cookie will travel
  // alongside the request. Once the migration completes this branch is
  // removed entirely.
  const legacyToken = getLegacyToken();
  if (legacyToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${legacyToken}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}