// The one place that talks to the API. Every request carries the signed-in person's pass.
import { accessToken, signedOutByServer } from '@/lib/auth'
import { ShownError } from '@/lib/errors'

/** The server said no. `message` is always fit to show: the server's own words, or a fallback. */
export class ApiError extends ShownError {
  status: number
  /** The whole answer, for the few that carry more than a message. */
  body: unknown

  constructor(status: number, message: string, body: unknown = null) {
    super(message)
    this.status = status
    this.body = body
  }
}

// The server writes its reasons for people, as a string in `detail`. A list in `detail` is
// FastAPI refusing a malformed request, and no body at all is a crash: neither is for people.
function detailOf(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  // POST /inputs reports a failed extraction in `error`, with the note already saved.
  const error = (body as { error?: unknown } | null)?.error
  if (typeof error === 'string') return error
  return 'Something went wrong on our side. Try again in a minute.'
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
    if (e instanceof TypeError) throw new ShownError('No connection. Check your internet and try again.')
    if (e instanceof DOMException && e.name === 'TimeoutError') throw new ShownError('The server took too long to answer. Try again.')
    throw e
  }
  const body: unknown = await res.json().catch(() => null)
  // The pass was refused: the sign-in screen takes over.
  if (res.status === 401) signedOutByServer()
  if (!res.ok) throw new ApiError(res.status, detailOf(body), body)
  return body as T
}
