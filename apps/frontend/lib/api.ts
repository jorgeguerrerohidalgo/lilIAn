/**
 * Resuelve la URL base del backend según el contexto de ejecución.
 *
 * Orden de prioridad:
 *   1. ``NEXT_PUBLIC_API_URL`` (explícito, p.ej. tunnels de Cloudflare).
 *   2. Cadena vacía en el browser (mismo origen, rutas relativas).
 *   3. ``http://localhost:8000`` como fallback SSR.
 *
 * @returns URL base del backend (sin slash final).
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
 * Wrapper de fetch que selecciona la URL del API e incluye credenciales.
 *
 * Estrategia de auth (S0-04):
 * - Prefiere la cookie HttpOnly ``lilian_auth_token``, enviada
 *   automáticamente por el browser en requests same-origin.
 * - Fallback a ``Authorization: Bearer <jwt>`` legacy construido desde
 *   localStorage para mantener compatibilidad con código antiguo.
 * - Usa ``credentials: 'include'`` para que requests cross-origin
 *   sigan enviando la cookie una vez CORS esté endurecido.
 *
 * @param endpoint - Path del endpoint (ej: ``"/api/v1/matters"``).
 * @param options - Opciones adicionales de ``fetch``.
 * @returns Promesa con la respuesta parseada como JSON.
 * @throws Error si la respuesta HTTP no es OK, con el ``detail`` del backend.
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
