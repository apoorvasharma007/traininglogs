import type { ReactNode } from 'react'

/** A card whose title sits in a grey strip across its top, like Train's next-workout card.
 * `aside` is a short grey note on the right of the strip ("Shown first in Progress"). */
export default function SectionCard({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex min-h-11 items-center justify-between gap-3 bg-muted px-4">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {aside && <span className="text-[13px] text-muted-foreground">{aside}</span>}
      </div>
      {children}
    </section>
  )
}
