// Warm-up ramps: weight climbs and reps fall toward the first working set. Each step is a share
// of that set's weight; "bar" is the empty bar. Weights round to 2.5 kg and never go below the bar.

const BAR_KG = 20

type Step = { of: number | 'bar'; reps: number }

export const WARMUPS: { id: string; name: string; steps: Step[] }[] = [
  {
    id: 'full',
    name: 'Full ramp',
    steps: [
      { of: 'bar', reps: 10 },
      { of: 0.45, reps: 8 },
      { of: 0.65, reps: 5 },
      { of: 0.8, reps: 3 },
      { of: 0.9, reps: 1 },
    ],
  },
  {
    id: 'short',
    name: 'Short ramp',
    steps: [
      { of: 0.5, reps: 5 },
      { of: 0.7, reps: 4 },
      { of: 0.9, reps: 2 },
    ],
  },
  {
    id: '531',
    name: "Wendler's 5/3/1",
    steps: [
      { of: 0.4, reps: 5 },
      { of: 0.5, reps: 5 },
      { of: 0.6, reps: 3 },
    ],
  },
  { id: 'feeler', name: 'One feeler set', steps: [{ of: 0.5, reps: 10 }] },
]

/** The warmup sets for a ramp, given the first working set's weight in kg. */
export function warmupSets(id: string, workingKg: number): { kg: number; reps: number }[] {
  const ramp = WARMUPS.find((w) => w.id === id)
  if (!ramp) return []
  return ramp.steps.map((s) => ({
    kg: s.of === 'bar' ? BAR_KG : Math.max(BAR_KG, Math.round((workingKg * s.of) / 2.5) * 2.5),
    reps: s.reps,
  }))
}
