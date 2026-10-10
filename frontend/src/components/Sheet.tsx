import type { ReactNode } from 'react'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'

/**
 * A panel that slides up from the bottom (shadcn Drawer, built on vaul): drag it down, tap
 * outside or press Escape to close. `label` names it for screen readers. It grows with its
 * content up to the visible screen (dvh, not Safari's vh), and only scrolls beyond that.
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
  return (
    // repositionInputs off: on iPhone the library moved the sheet up for the keyboard while Safari
    // moved the page too, so a note box being typed in slid out of view.
    <Drawer open={open} onOpenChange={(next) => !next && onClose()} repositionInputs={false}>
      <DrawerContent aria-describedby={undefined} className="mx-auto max-w-md rounded-t-[28px] border-border bg-card/85 backdrop-blur-xl backdrop-saturate-150 data-[vaul-drawer-direction=bottom]:max-h-[calc(100dvh-2.5rem)]">
        <DrawerTitle className="sr-only">{label}</DrawerTitle>
        <div className="flex flex-col gap-4 overflow-y-auto px-5 pt-3 pb-[calc(env(safe-area-inset-bottom)+1.5rem)]">
          {children}
        </div>
      </DrawerContent>
    </Drawer>
  )
}
