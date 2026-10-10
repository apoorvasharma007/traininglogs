import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { accessToken } from '@/lib/auth'
import { fakeApi, renderApp } from '@/test-utils'

const SUPABASE = 'https://test.supabase.co/auth/v1'
const CONFIG = { 'GET /config': { supabase_url: 'https://test.supabase.co', supabase_publishable_key: 'sb_publishable_x' } }
const signedOut = () => localStorage.removeItem('tl_session')
const error = (status: number, body: object) => new Response(JSON.stringify(body), { status })

describe('Signing in', () => {
  it('emails a code, checks it, and opens the app', async () => {
    signedOut()
    const calls = fakeApi({
      ...CONFIG,
      [`POST ${SUPABASE}/otp`]: {},
      [`POST ${SUPABASE}/verify`]: { access_token: 'pass', refresh_token: 'renew', expires_in: 3600, user: { email: 'me@example.com' } },
      'GET /programs': [],
      'GET /sessions?limit=5': [],
    })
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), 'me@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Email Me a Code' }))
    expect(await screen.findByText('We sent a code to me@example.com.')).toBeInTheDocument()
    expect(calls.find((c) => c.key === `POST ${SUPABASE}/otp`)?.body).toEqual({ email: 'me@example.com', create_user: true })

    await userEvent.type(screen.getByLabelText('Code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    await waitFor(() => expect(screen.queryByLabelText('Code')).not.toBeInTheDocument())
    expect(calls.find((c) => c.key === `POST ${SUPABASE}/verify`)?.body).toEqual({ type: 'email', email: 'me@example.com', token: '123456' })
    expect(await accessToken()).toBe('pass')
  })

  it('says when an email is not invited', async () => {
    signedOut()
    fakeApi({ ...CONFIG, [`POST ${SUPABASE}/otp`]: () => error(422, { error_code: 'signup_disabled', msg: 'Signups not allowed for otp' }) })
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), 'stranger@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Email Me a Code' }))
    expect(await screen.findByRole('alert')).toHaveTextContent("This email isn't invited yet.")
  })

  it('says when a code is wrong, and keeps the email', async () => {
    signedOut()
    fakeApi({ ...CONFIG, [`POST ${SUPABASE}/otp`]: {}, [`POST ${SUPABASE}/verify`]: () => error(403, { error_code: 'otp_expired' }) })
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), 'me@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Email Me a Code' }))
    await userEvent.type(await screen.findByLabelText('Code'), '000000')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByRole('alert')).toHaveTextContent("That code didn't work. Check it, or send a new one.")
    expect(screen.getByText('We sent a code to me@example.com.')).toBeInTheDocument()
  })

  it('a pass the server refuses brings back the sign-in screen', async () => {
    fakeApi({ 'GET /programs': () => error(401, { detail: "You're signed out. Sign in again." }), 'GET /sessions?limit=5': [] })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Email Me a Code' })).toBeInTheDocument()
  })
})

describe('The pass', () => {
  const expiring = (refresh = 'renew') =>
    localStorage.setItem('tl_session', JSON.stringify({ access_token: 'old', refresh_token: refresh, expires_at: Date.now() + 10_000, email: 'me@example.com' }))

  it('is renewed shortly before it runs out, once even when asked for twice at once', async () => {
    expiring()
    const calls = fakeApi({ ...CONFIG, [`POST ${SUPABASE}/token?grant_type=refresh_token`]: { access_token: 'new', refresh_token: 'renew2', expires_in: 3600 } })
    expect(await Promise.all([accessToken(), accessToken()])).toEqual(['new', 'new'])
    expect(calls.filter((c) => c.key.includes('grant_type=refresh_token'))).toHaveLength(1)
    expect(await accessToken()).toBe('new')
  })

  it('a renewal Supabase refuses signs out', async () => {
    expiring()
    fakeApi({ ...CONFIG, [`POST ${SUPABASE}/token?grant_type=refresh_token`]: () => error(400, { error_code: 'refresh_token_not_found' }) })
    expect(await accessToken()).toBeNull()
    expect(localStorage.getItem('tl_session')).toBeNull()
  })

  it('offline, the old pass is still sent', async () => {
    expiring()
    localStorage.setItem('tl_config', JSON.stringify(CONFIG['GET /config']))
    globalThis.fetch = (async () => { throw new TypeError('Load failed') }) as typeof fetch
    expect(await accessToken()).toBe('old')
  })
})

describe('Signing out', () => {
  it('asks first, warns about sessions not sent yet, then shows the sign-in screen', async () => {
    const { enqueue } = await import('@/lib/store')
    fakeApi({ ...CONFIG, 'GET /progress/lifts': { key_lifts: [], other_lifts: [] }, [`POST ${SUPABASE}/logout`]: {} })
    await enqueue({ client_id: 'c'.repeat(32) } as never).catch(() => undefined)
    renderApp('/settings')
    expect(await screen.findByText('a@example.com')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sign Out' }))
    const sheet = await screen.findByRole('dialog', { name: 'Sign Out?' })
    expect(sheet).toHaveTextContent("1 session hasn't sent yet. It stays on this phone and sends after you sign in again.")
    await userEvent.click(within(sheet).getByRole('button', { name: 'Sign Out' }))
    expect(await screen.findByRole('button', { name: 'Email Me a Code' })).toBeInTheDocument()
    expect(localStorage.getItem('tl_session')).toBeNull()
  })
})
