import { motion } from 'motion/react'
import { useState } from 'react'
import Sheet from '@/components/Sheet'
import { EFFORT_FILL, EFFORTS } from '@/lib/effort'

export type EffortTarget = { setKey: string; exercise: string; set: string; did: string }

/**
 * Asked right after a working set is ticked: how hard was it? Three big coloured answers; one tap
 * saves it and closes. Swiping the sheet down skips. Stays mounted so it slides in and out.
 */
export default function EffortSheet({
  target,
  onPick,
  onClose,
}: {
  target: EffortTarget | null
  onPick: (setKey: string, rpe: number) => void
  onClose: () => void
}) {
  // Keeps showing the set while the sheet slides away.
  const [shown, setShown] = useState(target)
  if (target && target !== shown) setShown(target)
  return (
    <Sheet open={target != null} onClose={onClose} label="How hard was it?">
      {shown && (
        <>
          <div className="flex flex-col gap-0.5">
            <span className="text-[13px] font-semibold text-muted-foreground">
              {shown.exercise}, set {shown.set}{shown.did && `: ${shown.did}`}
            </span>
            <span className="text-[22px] font-bold tracking-tight">How hard was it?</span>
          </div>
          <div className="flex flex-col gap-2.5">
            {EFFORTS.map((e, i) => (
              <motion.button key={e.level} type="button"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.04 * i, duration: 0.2 }}
                onClick={() => { navigator.vibrate?.(10); onPick(shown.setKey, e.rpe) }}
                className={`flex h-18 items-center justify-between rounded-2xl px-5 text-left transition active:scale-[0.97] ${EFFORT_FILL[e.level]}`}>
                <span className="flex flex-col">
                  <span className="text-[19px] font-bold">{e.label}</span>
                  {e.means && <span className="text-[13px] opacity-80">{e.means}</span>}
                </span>
                <Meter level={e.level} />
              </motion.button>
            ))}
          </div>
          <p className="text-center text-xs text-muted-foreground">Swipe down to skip</p>
        </>
      )}
    </Sheet>
  )
}

/** One, two or three bars, in the tile's own colour. */
function Meter({ level }: { level: number }) {
  return (
    <span aria-hidden className="flex items-end gap-1">
      {[12, 20, 28].map((h, i) => (
        <span key={h} style={{ height: h }} className={`w-1.5 rounded-sm bg-current ${i < level ? '' : 'opacity-25'}`} />
      ))}
    </span>
  )
}
