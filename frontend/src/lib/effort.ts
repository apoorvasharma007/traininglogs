// Effort in words, for people who don't use RPE. Each word is stored as one RPE number, so the
// estimated-max maths (reps left = 10 - RPE) keeps working; an exact RPE is still possible.

export const EFFORTS = [
  { level: 1, label: 'Moderate', rpe: 7, means: 'Could do 3+ more' },
  { level: 2, label: 'Hard', rpe: 8.5, means: 'Could do 1 or 2 more' },
  { level: 3, label: 'All Out', rpe: 10, means: "Couldn't do another" },
] as const

/** A chosen effort's fill, and the outline of an RPE number not chosen: sage green (Moderate),
 * ochre (Hard) and red (All Out), Apoorva's palette. Dark text on the green and ochre, which are
 * too light for white text to read; white on the red. */
export const EFFORT_FILL = {
  1: 'bg-[#37B24D] text-stone-900',
  2: 'bg-[#E67E22] text-stone-900',
  3: 'bg-[#C92A2A] text-white',
} as const

export const EFFORT_OUTLINE = { 1: 'border-[#37B24D]', 2: 'border-[#E67E22]', 3: 'border-[#C92A2A]' } as const

/** 1 (Moderate) for RPE up to 7.5, 2 (Hard) for 8 to 9, 3 (All out) from 9.5; 0 without RPE. */
export function effortLevel(rpe: number | null | undefined): 0 | 1 | 2 | 3 {
  if (rpe == null) return 0
  if (rpe < 8) return 1
  if (rpe < 9.5) return 2
  return 3
}
