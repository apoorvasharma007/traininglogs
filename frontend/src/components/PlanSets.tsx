import { workingText } from '@/lib/programs'
import type { PlanExercise } from '@/lib/types'

/** A planned exercise's sets, right-aligned so every row's working sets line up: the working sets,
 * and any warm-ups under them, smaller and fainter. */
export default function PlanSets({ exercise: e }: { exercise: PlanExercise }) {
  return (
    <span className="flex shrink-0 flex-col items-end font-mono">
      <span className="text-[13px] text-foreground">{workingText(e)}</span>
      {e.warmup_sets > 0 && <span className="text-[11px] text-faint-foreground">+{e.warmup_sets} warm-up</span>}
    </span>
  )
}
