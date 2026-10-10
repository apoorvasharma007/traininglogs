import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** A sheet's list of actions or choices, on a grey background. Destructive ones go in a group of
 * their own, `danger`: solid red, apart from the rest, so they can't be tapped by mistake. Every
 * menu and every "pick one" list in the app is built from this and MenuItem. */
export function MenuGroup({ danger, children }: { danger?: boolean; children: ReactNode }) {
  return (
    <div className={cn('flex flex-col overflow-hidden rounded-2xl', danger ? 'bg-destructive text-white' : 'bg-muted')}>
      {children}
    </div>
  )
}

/** One action or choice: an optional icon in a small tile, its name, an optional grey line under
 * it (`detail`) and an optional note on the right (`aside`, like "Next"). */
export function MenuItem({ icon: Icon, label, detail, aside, danger, disabled, onClick }: {
  icon?: LucideIcon
  label: string
  detail?: ReactNode
  aside?: ReactNode
  danger?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={cn('flex min-h-14 items-center gap-3.5 border-t border-border/60 px-4 py-2.5 text-left first:border-t-0 disabled:opacity-40',
        danger ? 'active:bg-black/10' : 'active:bg-border/60')}>
      {Icon && (
        <span className={cn('flex size-8.5 shrink-0 items-center justify-center rounded-xl', danger ? 'bg-white/15' : 'bg-card')}>
          <Icon size={18} aria-hidden />
        </span>
      )}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-base font-semibold">{label}</span>
        {detail && <span className="text-[13px] text-muted-foreground">{detail}</span>}
      </span>
      {aside && <span className="shrink-0 text-[13px] text-muted-foreground">{aside}</span>}
    </button>
  )
}
