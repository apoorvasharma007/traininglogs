import { Check } from 'lucide-react'
import { useState } from 'react'
import NoteBox from '@/components/NoteBox'
import Sheet from '@/components/Sheet'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { BTN, SHEET_TITLE } from '@/lib/ui'

const KINDS = [
  { kind: 'feature', label: 'Feature', placeholder: 'What would you like the app to do?' },
  { kind: 'bug', label: 'Problem', placeholder: 'What went wrong, and on which screen?' },
  { kind: 'other', label: 'Other', placeholder: "What's on your mind?" },
] as const

/** Send a feature request, a problem or anything else from Settings. Saved with the sender and the
 * app's version, so Apoorva can read it and reply. */
export default function FeedbackSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} label="Send Feedback">
      {/* A fresh form each time the sheet opens. */}
      {open && <FeedbackForm onClose={onClose} />}
    </Sheet>
  )
}

function FeedbackForm({ onClose }: { onClose: () => void }) {
  const [kind, setKind] = useState<(typeof KINDS)[number]['kind']>('feature')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  async function send() {
    setBusy(true)
    setError(null)
    try {
      await api('/feedback', { method: 'POST', body: { kind, message } })
      setSent(true)
    } catch (e) {
      setError(errorText(e))
    }
    setBusy(false)
  }

  if (sent) {
    return (
      <>
        <div className="flex flex-col items-center gap-2.5 pt-2 text-center">
          <span className="flex size-13 items-center justify-center rounded-2xl bg-highlight-soft text-highlight">
            <Check size={22} strokeWidth={2.6} aria-hidden />
          </span>
          <span className={SHEET_TITLE}>Sent. Thank You.</span>
        </div>
        <button type="button" onClick={onClose} className={BTN.primary}>Done</button>
      </>
    )
  }

  return (
    <>
      <span className={SHEET_TITLE}>Send Feedback</span>
      <div role="group" aria-label="Kind" className="grid grid-cols-3 gap-1 rounded-2xl bg-muted p-1">
        {KINDS.map((k) => (
          <button key={k.kind} type="button" aria-pressed={kind === k.kind} onClick={() => setKind(k.kind)}
            className={`h-11 rounded-xl text-[15px] font-semibold ${kind === k.kind ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'}`}>
            {k.label}
          </button>
        ))}
      </div>
      <label htmlFor="feedback-message" className="sr-only">Message</label>
      <NoteBox id="feedback-message" value={message} onChange={(e) => setMessage(e.target.value)}
        placeholder={KINDS.find((k) => k.kind === kind)!.placeholder}
        className="min-h-32 rounded-2xl bg-muted px-3.5 py-3 text-[15px] placeholder:text-faint-foreground" />
      {error && <p role="alert" className="text-[15px] text-destructive">{error}</p>}
      <button type="button" disabled={busy || !message.trim()} onClick={send} className={BTN.primary}>
        {busy ? 'Sending…' : 'Send'}
      </button>
    </>
  )
}
