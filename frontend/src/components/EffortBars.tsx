import { EFFORTS, effortLevel } from '@/lib/effort'

/** Effort as a small three-bar meter: one bar Moderate, two Hard, three All out. */
export default function EffortBars({ rpe }: { rpe: number | null }) {
  const level = effortLevel(rpe)
  if (!level) return null
  return (
    <span role="img" aria-label={`Effort: ${EFFORTS[level - 1].label}`} className="flex items-end gap-px">
      {[4, 7, 10].map((h, i) => (
        <span key={h} style={{ height: h }} className={`w-[3px] rounded-[1px] ${i < level ? 'bg-foreground' : 'bg-border'}`} />
      ))}
    </span>
  )
}
