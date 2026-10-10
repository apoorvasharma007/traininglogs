import type { ReactNode } from 'react'

/**
 * A screen's main action, fixed at the bottom where the thumb is. `aboveTabs` lifts it over the
 * tab bar on screens that show one. The spacer keeps the end of the page from hiding under it.
 */
export default function BottomBar({
  error,
  aboveTabs = false,
  children,
}: {
  error?: string | null
  aboveTabs?: boolean
  children: ReactNode
}) {
  return (
    <>
      <div aria-hidden className="h-24" />
      <div className={`fixed inset-x-0 z-20 border-t border-border bg-card/85 backdrop-blur-xl backdrop-saturate-150 ${aboveTabs ? 'bottom-[calc(4rem+env(safe-area-inset-bottom))]' : 'bottom-0'}`}>
        <div className={`mx-auto flex max-w-md flex-col gap-2 px-4 pt-3 ${aboveTabs ? 'pb-3' : 'pb-[calc(env(safe-area-inset-bottom)+1rem)]'}`}>
          {error && <p role="alert" className="text-[15px] text-destructive">{error}</p>}
          {children}
        </div>
      </div>
    </>
  )
}
