// What lives on the phone, in the browser's database (IndexedDB): the session in progress, and
// finished sessions waiting to be sent. Survives reloads, closing the browser and restarts.
// Each person's are kept under their email, so someone else signing in on this phone never sees
// them or sends them as their own.
import { del, get, set } from 'idb-keyval'
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import { api } from '@/lib/api'
import { signedInEmail } from '@/lib/auth'
import { errorText } from '@/lib/errors'
import type { LiveSession, SessionRequest } from '@/lib/session'

const CURRENT = 'session-in-progress'
const SEND_TIMEOUT_MS = 20_000
const OUTBOX = 'sessions-to-send'
const mine = (key: string) => `${key}:${signedInEmail()}`

export async function loadSession(): Promise<LiveSession | null> {
  return (await get<LiveSession>(mine(CURRENT))) ?? null
}

export async function saveSession(session: LiveSession | null): Promise<void> {
  if (session) await set(mine(CURRENT), session)
  else await del(mine(CURRENT))
}

/**
 * The session in progress, saved on every change. `session` is undefined while it loads from
 * the phone, then the session or null.
 */
export function useLiveSession() {
  const [session, setSession] = useState<LiveSession | null | undefined>(undefined)
  useEffect(() => {
    loadSession().then(setSession)
  }, [])
  const update = useCallback((next: LiveSession | null) => {
    setSession(next)
    saveSession(next)
  }, [])
  return { session, update }
}

// ---- the outbox: finished sessions until the server has them ----

type Outbox = { pending: SessionRequest[]; sending: boolean; lastError: string | null }
let outbox: Outbox = { pending: [], sending: false, lastError: null }
const listeners = new Set<() => void>()

function publish(next: Partial<Outbox>) {
  outbox = { ...outbox, ...next }
  listeners.forEach((l) => l())
}

async function readOutbox(): Promise<SessionRequest[]> {
  return (await get<SessionRequest[]>(mine(OUTBOX))) ?? []
}

export async function enqueue(request: SessionRequest): Promise<void> {
  const pending = (await readOutbox()).filter((r) => r.client_id !== request.client_id)
  pending.push(request)
  await set(mine(OUTBOX), pending)
  publish({ pending })
}

/** Sends every waiting session, oldest first. Stops at the first failure and keeps the rest. */
export async function flush(): Promise<void> {
  // Signed out: nothing is sent until the owner signs in again.
  if (outbox.sending || !signedInEmail()) return
  publish({ sending: true, pending: await readOutbox() })
  try {
    for (const request of [...outbox.pending]) {
      // A send that hangs counts as failed after 20 s, so later retries aren't blocked behind it.
      await api('/sessions', { method: 'POST', body: request, timeoutMs: SEND_TIMEOUT_MS })
      const pending = (await readOutbox()).filter((r) => r.client_id !== request.client_id)
      await set(mine(OUTBOX), pending)
      publish({ pending, lastError: null })
    }
  } catch (e) {
    publish({ lastError: errorText(e, "Couldn't send. It will try again.") })
  } finally {
    publish({ sending: false })
  }
}

/** Sends waiting sessions when the app opens and whenever the phone comes back online. */
export function startOutbox(): () => void {
  flush()
  const onOnline = () => flush()
  window.addEventListener('online', onOnline)
  return () => window.removeEventListener('online', onOnline)
}

/** For tests: forget the in-memory queue state between tests. */
export function resetOutboxForTests(): void {
  outbox = { pending: [], sending: false, lastError: null }
}

export function useOutbox(): Outbox {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => outbox,
  )
}
