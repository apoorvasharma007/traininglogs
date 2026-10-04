import type { ReactNode } from 'react'

/** The big title at the top of a tab's main screen, with an optional line under it. */
export default function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 px-1 pt-12">
      <h1 className="text-[28px] font-bold tracking-tight">{children}</h1>
      {sub && <p className="text-[13px] text-muted-foreground">{sub}</p>}
    </div>
  )
}
