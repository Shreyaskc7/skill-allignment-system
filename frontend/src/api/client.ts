/**
 * API client.
 *
 * - The access token lives in memory only (never localStorage), limiting what injected scripts can steal.
 * - The refresh token is an HttpOnly, SameSite=Strict cookie the browser sends only to /api/v1/auth.
 * - Any 401 triggers one silent refresh (shared between concurrent requests) and a single retry.
 *
 * By default requests are same-origin (`/api/...`): the Vite dev server proxies them to FastAPI,
 * and production should serve both behind one origin. VITE_API_BASE_URL overrides this.
 */
export const API = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
let onSessionExpired: () => void = () => {};

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

type ValidationItem = { loc?: (string | number)[]; msg?: string };

async function toError(r: Response): Promise<ApiError> {
  let message = r.status === 429 ? 'Too many attempts. Please wait a minute and try again.' : 'Request failed';
  const fieldErrors: Record<string, string> = {};
  try {
    const body = await r.json();
    if (typeof body.detail === 'string') message = body.detail;
    else if (Array.isArray(body.detail)) {
      for (const item of body.detail as ValidationItem[]) {
        const field = String(item.loc?.[item.loc.length - 1] ?? '');
        const msg = (item.msg ?? 'Invalid value').replace(/^Value error, /, '');
        if (field && !fieldErrors[field]) fieldErrors[field] = msg;
      }
      message = Object.values(fieldErrors)[0] || 'Please check the highlighted fields.';
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(message, r.status, fieldErrors);
}

let inflightRefresh: Promise<unknown> | null = null;

async function doRefresh(): Promise<unknown> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await fetch(`${API}/api/v1/auth/refresh`, { method: 'POST', credentials: 'include' });
    if (r.ok) {
      const body = await r.json();
      accessToken = body.access_token;
      return body;
    }
    // Another tab may have just rotated the shared cookie; give the browser a moment and retry once.
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  accessToken = null;
  return null;
}

/**
 * Exchange the refresh cookie for a new access token. Returns the session body or null.
 * Concurrent callers share one request, so a token is never presented twice by this tab.
 */
export function refreshSession<T = { access_token: string }>(): Promise<T | null> {
  inflightRefresh ??= doRefresh().finally(() => {
    inflightRefresh = null;
  });
  return inflightRefresh as Promise<T | null>;
}

function refreshOnce(): Promise<string | null> {
  refreshing ??= refreshSession()
    .then(() => accessToken)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** Fetch JSON from the API with authentication, throwing ApiError on failure. */
export async function request<T = unknown>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const r = await fetch(API + path, { ...init, headers, credentials: 'include' });
  if (r.status === 401 && retry && !path.startsWith('/api/v1/auth/')) {
    if (await refreshOnce()) return request<T>(path, init, false);
    onSessionExpired();
  }
  if (!r.ok) throw await toError(r);
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Authenticated binary download (e.g. profile photo) as an object URL. Caller revokes it. */
export async function requestObjectUrl(path: string): Promise<string | null> {
  const headers = new Headers();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const r = await fetch(API + path, { headers, credentials: 'include' });
  if (!r.ok) return null;
  return URL.createObjectURL(await r.blob());
}

export function putJson<T = unknown>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

export function uploadFile<T = unknown>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append('file', file);
  return request<T>(path, { method: 'POST', body: fd });
}
