import { useState } from 'react'
import { useLocation } from 'wouter'
import ScreenHeader from '@/components/ScreenHeader'
import BottomBar from '@/components/BottomBar'
import { api } from '@/lib/api'
import { localDate } from '@/lib/session'
import type { CaptureOut } from '@/lib/types'
import { errorText, ShownError } from '@/lib/errors'

/** Paste a written note; AI reads it into sets, then Review shows them for checking. */
export default function LogFromNotes() {
  const [, navigate] = useLocation()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function extract() {
    if (!text.trim()) return
    setBusy(true)
    setError(null)
    try {
      const out = await api<CaptureOut>('/inputs', { method: 'POST', body: { content: text, date: localDate(new Date()) } })
      if (!out.extraction_id) throw new ShownError(out.error ?? "Couldn't read your note. It's saved, so nothing is lost. Try again in a minute.")
      navigate(`/review/${out.extraction_id}`)
    } catch (e) {
      setError(errorText(e))
      setBusy(false)
    }
  }

  return (
    <div>
      <ScreenHeader back="/" backLabel="Back to Train" title="Log from Notes" />
      <div className="flex flex-col gap-2.5">
        <label htmlFor="session-text" className="sr-only">
          What did you do?
        </label>
        <textarea
          id="session-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"Paste from Notes, copy text from a photo of your notebook (Live Text), or type or dictate it.\n\nSquat 3x5 at 100\nBench 80 x 8, 8, 6, last one was a grind\nPull-ups 10, 8, 7 with bodyweight\nRDL 60kg 3 sets of 10, lower back felt tight\n5 min row to warm up"}
          className="h-[calc(100dvh-23rem)] min-h-52 resize-none rounded-2xl border border-border bg-card p-3.5 leading-normal"
        />
      </div>
      <BottomBar aboveTabs error={error}>
        <button
          type="button"
          disabled={busy || !text.trim()}
          onClick={extract}
          className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
        >
          {busy ? 'Sending…' : 'Send'}
        </button>
        <p className="text-center text-xs text-muted-foreground">
          Reads your note with AI for about $0.02 to $0.06; longer notes cost more. Each AI fix after that is $0.01 to $0.04 more. You check everything before it's saved.
        </p>
      </BottomBar>
    </div>
  )
}
