// The one place that talks to the API. Every request carries the API key saved in Settings.

// Same storage key as the old web/ UI, so a key saved there works here too (same origin).
const KEY_STORAGE = 'tl_apiKey'

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? ''
  } catch {
    return ''
  }
}

export function setApiKey(key: string): void {
  try {
    localStorage.setItem(KEY_STORAGE, key)
  } catch {
    // Storage blocked (private mode): the key lasts until the page closes.
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI puts the reason in `detail`: a string, or a list of validation errors.
function detailOf(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  // POST /inputs reports a failed extraction in `error`, with the note already saved.
  const error = (body as { error?: unknown } | null)?.error
  if (typeof error === 'string') return error
  if (status === 401) return 'The API key is missing or wrong. Set it in Settings.'
  return `Request failed (${status})`
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const res = await fetch(path, {
    method: init?.method ?? 'GET',
    headers: { 'Content-Type': 'application/json', 'X-Api-Key': getApiKey() },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  })
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailOf(body, res.status))
  return body as T
}
