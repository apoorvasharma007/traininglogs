import { Check } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { MenuGroup, MenuItem } from '@/components/Menu'
import { type MarkMode, markOf, musclesOf } from '@/lib/muscleMarks'

/** A group's muscles in a bubble pointing at the tapped point (x, y inside a box w by h). It opens
 *  to the side away from the box's nearer edge and closes on any tap outside it. */
export default function MuscleBubble({ group, at, mode, primary, secondary, onPick, onClose }: {
  group: string
  at: { x: number; y: number; w: number; h: number }
  mode: MarkMode
  primary: string[]
  secondary: string[]
  onPick: (muscle: string) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: PointerEvent) => { if (!ref.current!.contains(e.target as Node)) onClose() }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [onClose])

  const opensRight = at.x < at.w / 2
  const opensDown = at.y < at.h / 2
  const gap = 10
  return (
    <div ref={ref} className="absolute z-10 flex w-max flex-col gap-1.5 rounded-3xl border border-border bg-card p-2 shadow-lg"
      style={{
        ...(opensRight ? { left: at.x + gap } : { right: at.w - at.x + gap }),
        ...(opensDown ? { top: at.y - 20 } : { bottom: at.h - at.y - 20 }),
        maxWidth: (opensRight ? at.w - at.x : at.x) - gap,
      }}>
      <span aria-hidden className={`absolute size-3 rotate-45 border-border bg-card ${
        opensRight ? '-left-1.5 border-b border-l' : '-right-1.5 border-t border-r'} ${opensDown ? 'top-3.5' : 'bottom-3.5'}`} />
      <p className="px-4 pt-1 text-[13px] font-semibold text-muted-foreground">{group}</p>
      <MenuGroup>
        {musclesOf(group).map((m) => {
          const mark = markOf(primary, secondary, [m])
          // A tick for what this body marks; a muscle marked on the other body says which.
          const aside = mark === mode ? <Check size={18} aria-hidden className="text-highlight" /> : mark === 'primary' ? 'Primary' : mark && 'Secondary'
          return <MenuItem key={m} label={m} aside={aside} onClick={() => onPick(m)} />
        })}
      </MenuGroup>
    </div>
  )
}
