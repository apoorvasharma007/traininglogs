import { ChevronDown } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'

/** Content that slides open and closed. Every open/close in the app uses this and `Chevron`. */
export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }} className="overflow-hidden">
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/** The open/close arrow: points down when closed, turns up when open. */
export function Chevron({ open, size = 16, className = '' }: { open: boolean; size?: number; className?: string }) {
  return (
    <ChevronDown size={size} aria-hidden
      className={`shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''} ${className}`} />
  )
}
