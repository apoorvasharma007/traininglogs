import Sheet from '@/components/Sheet'

/**
 * Asks before something that changes what's saved. "danger" (red) for removing things; "primary"
 * for changes that keep everything but alter what happens next, like updating a program.
 */
export default function ConfirmSheet({
  open,
  title,
  body,
  confirmLabel,
  busy,
  tone = 'danger',
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  body: string
  confirmLabel: string
  busy?: boolean
  tone?: 'danger' | 'primary'
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
        className={`h-13 rounded-2xl font-semibold transition active:scale-[0.98] disabled:opacity-50 ${
          tone === 'danger' ? 'bg-destructive text-white' : 'bg-primary text-primary-foreground'
        }`}>
        {busy ? 'Working…' : confirmLabel}
      </button>
      <button type="button" onClick={onClose} className="h-12 rounded-2xl border border-border font-semibold">
        Cancel
      </button>
    </Sheet>
  )
}
