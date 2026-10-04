import Sheet from '@/components/Sheet'

/** Asks before something that can't be undone from the app. */
export default function ConfirmSheet({
  open,
  title,
  body,
  confirmLabel,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  body: string
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Sheet open={open} onClose={onClose} label={title}>
      <div className="flex flex-col gap-1.5">
        <span className="text-[17px] font-semibold">{title}</span>
        <p className="text-sm text-muted-foreground">{body}</p>
      </div>
      <button type="button" disabled={busy} onClick={onConfirm}
        className="h-13 rounded-2xl bg-destructive font-semibold text-white transition active:scale-[0.98] disabled:opacity-50">
        {busy ? 'Working…' : confirmLabel}
      </button>
      <button type="button" onClick={onClose} className="h-12 rounded-2xl border border-border font-semibold">
        Cancel
      </button>
    </Sheet>
  )
}
