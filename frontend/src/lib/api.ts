// Calls the Flask API (backend/server.py) through this app's /api rewrite.

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: init.method || (init.body === undefined ? 'GET' : 'POST'),
      headers: init.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    // Network down or the server not running
    throw new ApiError('Cannot reach the RIA server', 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError((data && data.error) || `Request failed (${res.status})`, res.status);
  }
  return data as T;
}
