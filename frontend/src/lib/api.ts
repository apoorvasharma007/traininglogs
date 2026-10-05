// The one place that talks to the API. Every request carries the signed-in person's pass.
import { accessToken, signedOutByServer } from '@/lib/auth'

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
  return `Server error (${status}). Try again in a minute.`
}

export async function api<T>(
  path: string,
  init?: { method?: string; body?: unknown; timeoutMs?: number },
): Promise<T> {
  const token = await accessToken()
  let res: Response
  try {
    res = await fetch(path, {
      method: init?.method ?? 'GET',
      // A request that never answers would otherwise wait forever (no timeout by default).
      signal: init?.timeoutMs ? AbortSignal.timeout(init.timeoutMs) : undefined,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch (e) {
    // fetch rejects with a TypeError when the request never reaches the server; each browser
    // words it differently ("Load failed", "Failed to fetch").
    if (e instanceof TypeError) throw new Error('No connection. Check your internet and try again.')
    throw e
  }
  const body: unknown = await res.json().catch(() => null)
  // The pass was refused: the sign-in screen takes over.
  if (res.status === 401) signedOutByServer()
  if (!res.ok) throw new ApiError(res.status, detailOf(body, res.status))
  return body as T
}
