export const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

/** Fetch JSON from the API, throwing the server's `detail` message on failure. */
export async function request<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, init);
  if (!r.ok) {
    let message = 'Request failed';
    try {
      message = (await r.json()).detail || message;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(message);
  }
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
