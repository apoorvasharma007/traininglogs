import { useEffect, useState } from 'react'

// Shown in turn inside the empty box: what a good, detailed correction looks like.
const EXAMPLES = [
  'Squats were 4 sets, not 3. The last set was 120 kg for 3 reps.',
  'Bench was 80 kg on every set, and set 2 was only 6 reps because I failed the 7th.',
  'I skipped deadlifts today. Take them out and add 3 sets of 10 back extensions at 20 kg.',
  'This was yesterday, Saturday 3 October, and it took about 70 minutes.',
  'Add two warm-up sets to squats, 60 kg for 5 and 80 kg for 3, before the working sets.',
  'Pull-ups were bodyweight, not 10 kg. I did 8, 7 and 6 reps.',
]

/** Tell the AI everything to change, in one detailed message: each fix is a paid call. */
export default function FixBox({
  busy,
  error,
  onEdit,
  onFix,
}: {
  busy: boolean
  /** Why the last fix failed, one problem per line; it stays until the message changes. */
  error: string | null
  onEdit: () => void
  onFix: (text: string) => Promise<boolean>
}) {
  const [text, setText] = useState('')
  const [example, setExample] = useState(0)

  useEffect(() => {
    if (text || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = setInterval(() => setExample((i) => (i + 1) % EXAMPLES.length), 4000)
    return () => clearInterval(id)
  }, [text])

  return (
    <form
      className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (text.trim() && (await onFix(text.trim()))) setText('')
      }}
    >
      <div className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold">Got something wrong?</span>
        <span className="text-[13px] leading-snug text-muted-foreground">
          Describe everything you want changed in one message. Each fix is a paid AI call, so the more detail you give, the
          more likely it gets everything right first time.
        </span>
      </div>
      <div className="relative">
        <label htmlFor="fix" className="sr-only">
          What to change
        </label>
        <textarea id="fix" rows={4} value={text} onChange={(e) => { setText(e.target.value); onEdit() }}
          className="w-full resize-none rounded-xl bg-muted px-3.5 py-2.5 text-[15px] leading-snug" />
        {!text && (
          <span key={example} aria-hidden
            className="pointer-events-none absolute top-2.5 right-3.5 left-3.5 animate-in fade-in text-[15px] leading-snug text-faint-foreground duration-500">
            {EXAMPLES[example]}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground">Tip: tap the mic on your keyboard to say it instead.</span>
        <button type="submit" disabled={busy || !text.trim()}
          className="h-10 shrink-0 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-40">
          {busy ? 'Fixing…' : 'Fix It'}
        </button>
      </div>
      {error && (
        <div role="alert" className="flex flex-col gap-1 text-sm text-destructive">
          <span className="font-semibold">Couldn't make that fix, so nothing changed.</span>
          {error.split('\n').map((line) => (
            <span key={line}>{line}</span>
          ))}
          <span>Your message is still here to change and send again.</span>
        </div>
      )}
    </form>
  )
}
