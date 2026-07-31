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

/**
 * Fetch wrapper that auto-selects API URL
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const baseUrl = getApiUrl();
  const url = baseUrl ? `${baseUrl}${endpoint}` : endpoint;

  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}
