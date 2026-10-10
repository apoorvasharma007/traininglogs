import { ChevronLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'wouter'

/** A sub-screen's top bar: back link, title, optional action on the right. */
export default function ScreenHeader({
  back,
  backLabel,
  title,
  action,
  titleSlot,
}: {
  back?: string // left out while editing, so a draft can't be left by accident
  backLabel: string
  title: string
  action?: ReactNode
  /** Shown instead of the title, e.g. the name as a field while editing. */
  titleSlot?: ReactNode
}) {
  return (
    <header className="sticky top-0 z-10 -mx-4 mb-4 flex items-center gap-1 bg-muted/85 px-3 pt-3 pb-2 backdrop-blur-xl backdrop-saturate-150">
      {back ? (
        <Link href={back} aria-label={backLabel} className="flex size-11 items-center justify-center">
          <ChevronLeft size={22} strokeWidth={1.8} aria-hidden />
        </Link>
      ) : (
        <span className="w-1" />
      )}
      {titleSlot ?? <h1 className="flex-1 truncate text-[17px] font-semibold">{title}</h1>}
      {action}
    </header>
  )
}
