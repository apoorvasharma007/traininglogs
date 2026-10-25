import { X } from 'lucide-react'
import { useAnimate, useReducedMotion } from 'motion/react'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import BodyFigure from '@/components/BodyFigure'
import MuscleBubble from '@/components/MuscleBubble'
import { type MarkMode, mark, markOf, musclesOf, tapGroup } from '@/lib/muscleMarks'

/** A custom exercise's muscles, picked on a body: tap a shape and its group's muscles open in the
 *  bubble (a group whose muscles do one job is marked whole first). Taps mark `mode` (the sheet shows one body for primary, another for secondary);
 *  both kinds stay coloured so either body shows the whole exercise. A change of `nudge` with no
 *  primary muscle shakes the body to ask for one. */
export default function BodyMuscles({ mode, primary, secondary, onChange, nudge = 0 }: {
  mode: MarkMode
  primary: string[]
  secondary: string[]
  onChange: (primary: string[], secondary: string[]) => void
  nudge?: number
}) {
  const [open, setOpen] = useState<{ group: string; at: { x: number; y: number; w: number; h: number } } | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const [shaken, animate] = useAnimate()
  const reduceMotion = useReducedMotion()

  const pick = (muscle: string) => onChange(...mark(primary, secondary, muscle, mode))
  const tap = ({ group, clientX, clientY }: { group: string | null; clientX: number; clientY: number }) => {
    if (!group) return
    const muscles = musclesOf(group)
    if (muscles.length === 1) return pick(muscles[0])
    onChange(...tapGroup(primary, secondary, group, mode))
    const r = box.current!.getBoundingClientRect()
    setOpen({ group, at: { x: clientX - r.left, y: clientY - r.top, w: r.width, h: r.height } })
  }
  const shake = useEffectEvent(() => {
    if (primary.length === 0 && !reduceMotion) animate(shaken.current, { x: [0, -10, 10, -6, 6, 0] }, { duration: 0.4 })
  })
  useEffect(() => { if (nudge > 0) shake() }, [nudge])

  return (
    <div className="flex flex-col items-center gap-3">
      <div ref={box} className="relative w-full">
        <div ref={shaken} className="grid grid-cols-2 items-start gap-x-10 gap-y-1 px-4">
          {(['front', 'back'] as const).map((side) => (
            <BodyFigure key={side} side={side} focus={open?.group ?? null} markOfGroup={(g) => markOf(primary, secondary, musclesOf(g))} onTap={tap} />
          ))}
          <span className="text-center text-[11px] text-muted-foreground">Front</span>
          <span className="text-center text-[11px] text-muted-foreground">Back</span>
        </div>
        {nudge > 0 && primary.length === 0 && <span className="absolute top-0 left-0 text-[13px] text-muted-foreground">Tap a body part</span>}
        {open && <MuscleBubble group={open.group} at={open.at} mode={mode} primary={primary} secondary={secondary}
          onPick={pick} onClose={() => setOpen(null)} />}
      </div>
      {/* What this body marks, one tap each to take a muscle off. */}
      <div className="flex flex-wrap justify-center gap-1.5">
        {(mode === 'primary' ? primary : secondary).map((m) => (
          <button key={m} type="button" aria-label={`Remove ${m}`} onClick={() => pick(m)}
            className="flex h-8 items-center gap-1 rounded-full bg-highlight-soft pr-2 pl-3 text-[13px] font-medium text-highlight">
            {m}
            <X size={14} aria-hidden />
          </button>
        ))}
      </div>
    </div>
  )
}
