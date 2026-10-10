import { Trash2 } from 'lucide-react'
import Sheet from '@/components/Sheet'
import { BTN, SHEET_TITLE } from '@/lib/ui'

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
  busyLabel = 'Saving…',
  tone = 'danger',
  cancelLabel = 'Cancel',
  error,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  body: string
  confirmLabel: string
  busy?: boolean
  /** What the confirm button says while it waits: "Deleting…", "Following…". */
  busyLabel?: string
  tone?: 'danger' | 'primary'
  cancelLabel?: string
  /** The confirm failed: said here, where it was tapped. */
  error?: string
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Sheet open={open} onClose={onClose} label={title}>
      <div className="flex flex-col items-center gap-2.5 px-2 pt-1 text-center">
        {tone === 'danger' && (
          <span className="flex size-13 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
            <Trash2 size={22} aria-hidden />
          </span>
        )}
        <span className={SHEET_TITLE}>{title}</span>
        <p className="text-[15px] leading-snug text-muted-foreground">{body}</p>
      </div>
      {error && <p role="alert" className="text-center text-[15px] text-destructive">{error}</p>}
      <div className="flex flex-col gap-2.5">
        <button type="button" disabled={busy} onClick={onConfirm} className={tone === 'danger' ? BTN.dangerFill : BTN.primary}>
          {busy ? busyLabel : confirmLabel}
        </button>
        <button type="button" onClick={onClose} className={BTN.secondary}>
          {cancelLabel}
        </button>
      </div>
    </Sheet>
  )
}
