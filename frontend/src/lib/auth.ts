// Signing in with a code by email, through Supabase's sign-in web API directly: three requests
// (send a code, check it, renew the pass) instead of a 24 KB library. A code rather than a link,
// because a link opens Safari, not the app on the home screen, and the two keep separate storage.
//
// The pass (a JWT) and its renewal token stay on this phone. The pass is renewed shortly before it
// runs out, so a person stays signed in; a renewal Supabase refuses signs them out.
import { useSyncExternalStore } from 'react'

type Config = { supabase_url: string; supabase_publishable_key: string; version?: string }
type Session = { access_token: string; refresh_token: string; expires_at: number; email: string }

const SESSION_KEY = 'tl_session'
const CONFIG_KEY = 'tl_config'
// Renew this long before the pass runs out, so a request never leaves with one about to expire.
const RENEW_BEFORE_MS = 60_000

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function write(key: string, value: unknown): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage blocked (private mode): signed in until the page closes.
  }
}

// Read from storage each time rather than kept in memory, so there's one copy of the truth.
const current = () => read<Session>(SESSION_KEY)
const listeners = new Set<() => void>()

function setSession(next: Session | null): void {
  write(SESSION_KEY, next)
  listeners.forEach((l) => l())
}

/** The signed-in person's email, or null. */
export const signedInEmail = (): string | null => current()?.email ?? null

/** The signed-in person's email, or null; re-renders when it changes. */
export function useSignedIn(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => current()?.email ?? null,
  )
}

/** Which Supabase project to sign in with, from the server; kept for offline starts. */
export async function config(): Promise<Config> {
  try {
    const res = await fetch('/config')
    if (res.ok) {
      const fresh = (await res.json()) as Config
      write(CONFIG_KEY, fresh)
      return fresh
    }
  } catch {
    // Offline: fall back to the copy from last time.
  }
  const kept = read<Config>(CONFIG_KEY)
  if (!kept) throw new Error('No connection. Check your internet and try again.')
  return kept
}

class AuthError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function auth(path: string, body: unknown, token?: string): Promise<Record<string, unknown>> {
  const { supabase_url, supabase_publishable_key } = await config()
  let res: Response
  try {
    res = await fetch(`${supabase_url}/auth/v1/${path}`, {
      method: 'POST',
      headers: {
        apikey: supabase_publishable_key,
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new AuthError(0, 'offline', 'No connection. Check your internet and try again.')
  }
  const reply = (await res.json().catch(() => ({}))) as Record<string, unknown>
  if (!res.ok) {
    const code = String(reply.error_code ?? reply.code ?? '')
    throw new AuthError(res.status, code, String(reply.msg ?? reply.error_description ?? reply.message ?? ''))
  }
  return reply
}

function sessionFrom(reply: Record<string, unknown>, email: string): Session {
  return {
    access_token: String(reply.access_token),
    refresh_token: String(reply.refresh_token),
    expires_at: Date.now() + Number(reply.expires_in) * 1000,
    email: String((reply.user as { email?: string } | undefined)?.email ?? email),
  }
}

/** Emails a sign-in code. Supabase's "allow new users to sign up" setting decides whether a new
 * email gets one (invite only when off). */
export async function sendCode(email: string): Promise<void> {
  try {
    await auth('otp', { email, create_user: true })
  } catch (e) {
    if (!(e instanceof AuthError)) throw e
    if (e.status === 0) throw e
    if (e.code === 'signup_disabled' || e.code === 'otp_disabled' || /signups? not allowed/i.test(e.message)) {
      throw new Error("This email isn't invited yet.")
    }
    if (e.status === 429) throw new Error('Too many codes asked for. Wait a few minutes and try again.')
    throw new Error("Couldn't send the code. Try again in a minute.")
  }
}

/** Checks the emailed code; signs in when it's right. */
export async function verifyCode(email: string, code: string): Promise<void> {
  try {
    setSession(sessionFrom(await auth('verify', { type: 'email', email, token: code }), email))
  } catch (e) {
    if (e instanceof AuthError && e.status !== 0) throw new Error("That code didn't work. Check it, or send a new one.")
    throw e
  }
}

let renewing: Promise<string | null> | null = null

/** The pass to send with a request, renewed first when it's about to run out; null when signed out. */
export async function accessToken(): Promise<string | null> {
  const now = current()
  if (!now) return null
  if (now.expires_at - Date.now() > RENEW_BEFORE_MS) return now.access_token
  renewing ??= (async () => {
    try {
      const renewed = sessionFrom(await auth('token?grant_type=refresh_token', { refresh_token: now.refresh_token }), now.email)
      setSession(renewed)
      return renewed.access_token
    } catch (e) {
      // Offline: send the old pass; the server says if it's run out. Refused: signed out.
      if (e instanceof AuthError && e.status === 0) return now.access_token
      setSession(null)
      return null
    } finally {
      renewing = null
    }
  })()
  return renewing
}

/** The server refused the pass: show the sign-in screen. */
export function signedOutByServer(): void {
  setSession(null)
}

/** Signs out on this phone, and tells Supabase so the renewal token stops working. */
export async function signOut(): Promise<void> {
  const token = current()?.access_token
  setSession(null)
  if (token) await auth('logout', {}, token).catch(() => undefined)
}
