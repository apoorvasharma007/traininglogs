import { useState } from 'react'
import { sendCode, verifyCode } from '@/lib/auth'

/** Shown when nobody is signed in: an email, then the 6-digit code emailed to it. */
export default function SignIn() {
  const [email, setEmail] = useState('')
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(step: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await step()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  return (
    <form
      className="flex flex-col gap-4 pt-10"
      onSubmit={(e) => {
        e.preventDefault()
        if (sentTo) run(() => verifyCode(sentTo, code.trim()))
        else run(async () => {
          await sendCode(email.trim())
          setSentTo(email.trim())
        })
      }}
    >
      <div className="flex flex-col items-center gap-1 pb-4 text-center">
        <h1 className="text-[28px] font-bold tracking-tight">TrainingLogs</h1>
        <p className="text-sm text-muted-foreground">Log workouts however you like.</p>
        <p className="text-sm text-muted-foreground">We'll track your progress from them.</p>
      </div>
      {sentTo ? (
        <>
          <p className="px-1 text-sm text-muted-foreground">We sent a code to {sentTo}.</p>
          <label htmlFor="code" className="sr-only">
            Code
          </label>
          <input id="code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            inputMode="numeric" autoComplete="one-time-code" maxLength={10} autoFocus
            className="h-13 rounded-2xl border border-border bg-card px-4 font-mono text-[22px] tracking-[0.3em]" />
        </>
      ) : (
        <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4">
          <label htmlFor="email" className="text-[13px] font-semibold">
            Email
          </label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email" autoCapitalize="off" autoFocus
            className="h-11 rounded-xl border border-border bg-background px-3.5" />
        </div>
      )}
      {error && <p role="alert" className="px-1 text-sm text-destructive">{error}</p>}
      <button type="submit" disabled={busy || (sentTo ? code.trim().length < 6 : !email.includes('@'))}
        className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-50">
        {busy ? (sentTo ? 'Signing in…' : 'Sending…') : sentTo ? 'Sign in' : 'Email me a code'}
      </button>
      {sentTo && (
        <button type="button" onClick={() => { setSentTo(null); setCode(''); setError(null) }}
          className="h-11 text-sm font-semibold text-muted-foreground">
          Use a different email
        </button>
      )}
    </form>
  )
}
