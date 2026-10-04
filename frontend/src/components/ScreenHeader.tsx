import { ChevronLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'wouter'

/** A sub-screen's top bar: back link, title, optional action on the right. */
export default function ScreenHeader({
  back,
  backLabel,
  title,
  action,
}: {
  back: string
  backLabel: string
  title: string
  action?: ReactNode
}) {
  return (
    <header className="sticky top-0 z-10 -mx-4 mb-4 flex items-center gap-1 border-b border-border bg-background px-3 pt-3 pb-2">
      <Link href={back} aria-label={backLabel} className="flex size-11 items-center justify-center">
        <ChevronLeft size={22} strokeWidth={1.8} aria-hidden />
      </Link>
      <h1 className="flex-1 truncate text-[17px] font-semibold">{title}</h1>
      {action}
    </header>
  )
}
