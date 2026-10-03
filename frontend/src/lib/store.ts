// What lives on the phone, in the browser's database (IndexedDB): the session in progress, and
// finished sessions waiting to be sent. Survives reloads, closing the browser and restarts.
import { del, get, set } from 'idb-keyval'
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import { api } from '@/lib/api'
import type { LiveSession, SessionRequest } from '@/lib/session'

const CURRENT = 'session-in-progress'
const OUTBOX = 'sessions-to-send'

export async function loadSession(): Promise<LiveSession | null> {
  return (await get<LiveSession>(CURRENT)) ?? null
}

export async function saveSession(session: LiveSession | null): Promise<void> {
  if (session) await set(CURRENT, session)
  else await del(CURRENT)
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
  return (await get<SessionRequest[]>(OUTBOX)) ?? []
}

export async function enqueue(request: SessionRequest): Promise<void> {
  const pending = (await readOutbox()).filter((r) => r.client_id !== request.client_id)
  pending.push(request)
  await set(OUTBOX, pending)
  publish({ pending })
}

/** Sends every waiting session, oldest first. Stops at the first failure and keeps the rest. */
export async function flush(): Promise<void> {
  if (outbox.sending) return
  publish({ sending: true, pending: await readOutbox() })
  try {
    for (const request of [...outbox.pending]) {
      await api('/sessions', { method: 'POST', body: request })
      const pending = (await readOutbox()).filter((r) => r.client_id !== request.client_id)
      await set(OUTBOX, pending)
      publish({ pending, lastError: null })
    }
  } catch (e) {
    publish({ lastError: e instanceof Error ? e.message : String(e) })
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

export function useOutbox(): Outbox {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => outbox,
  )
}
