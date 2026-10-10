import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

/** How long Undo is offered before the bar goes by itself. */
export const UNDO_SECONDS = 6

/**
 * "Squat removed" with Undo, at the bottom of the screen. A small ring next to Undo empties over
 * UNDO_SECONDS, then the bar closes by itself. `key` it by what was removed, so a second removal
 * starts a fresh countdown.
 */
export default function UndoBar({ text, onUndo, onDismiss, className }: {
  text: string
  onUndo: () => void
  onDismiss: () => void
  className?: string
}) {
  // The countdown starts once, when the bar appears; redrawing the screen doesn't restart it.
  const dismiss = useRef(onDismiss)
  useEffect(() => {
    dismiss.current = onDismiss
  })
  useEffect(() => {
    const id = setTimeout(() => dismiss.current(), UNDO_SECONDS * 1000)
    return () => clearTimeout(id)
  }, [])

  return (
    <div role="status" className={cn('fixed inset-x-4 z-20 mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl bg-primary py-1.5 pr-1.5 pl-4 text-[15px] text-primary-foreground', className)}>
      <span>{text}</span>
      <span className="flex items-center">
        <button type="button" onClick={onUndo} className="flex h-10 items-center gap-2 px-3 font-bold text-highlight">
          <svg aria-hidden width="18" height="18" viewBox="0 0 20 20" className="-rotate-90">
            <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
            <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
              pathLength="100" strokeDasharray="100" className="undo-countdown" style={{ animationDuration: `${UNDO_SECONDS}s` }} />
          </svg>
          Undo
        </button>
        <button type="button" aria-label="Dismiss" onClick={onDismiss} className="h-10 px-3 opacity-70">
          ✕
        </button>
      </span>
    </div>
  )
}
