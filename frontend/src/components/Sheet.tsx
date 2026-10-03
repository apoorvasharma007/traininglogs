import { useEffect, useRef, type ReactNode } from 'react'

/**
 * A panel that slides up from the bottom, built on the browser's <dialog>: it traps focus,
 * closes on Escape, and dims the page behind it without any library. Tapping the dimmed area
 * closes it too.
 */
export default function Sheet({
  open,
  onClose,
  label,
  children,
}: {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal?.()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-label={label}
      onClose={onClose}
      onClick={(e) => {
        // A click on the dialog element itself (not its content) is a click on the backdrop.
        if (e.target === e.currentTarget) onClose()
      }}
      className="sheet mx-auto mt-auto mb-0 w-full max-w-md rounded-t-[20px] bg-card p-0 text-foreground backdrop:bg-black/45"
    >
      {open && (
        <div className="flex flex-col gap-4 px-5 pt-2 pb-[calc(env(safe-area-inset-bottom)+1.5rem)]">
          <div aria-hidden className="mx-auto h-1 w-9 rounded-full bg-border" />
          {children}
        </div>
      )}
    </dialog>
  )
}
