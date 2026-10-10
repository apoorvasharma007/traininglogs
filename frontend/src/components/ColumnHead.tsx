import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** The small grey column names over a table of sets (SET, KG, REPS…): the same look and the same
 * space above the rows on every screen. `className` gives the grid's columns. */
export default function ColumnHead({ className, children }: { className: string; children: ReactNode }) {
  return <div className={cn('grid items-end gap-1.5 pb-1.5 text-[11px] font-semibold tracking-wide text-faint-foreground', className)}>{children}</div>
}
