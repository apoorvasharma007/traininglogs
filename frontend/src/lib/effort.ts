// Effort in words, for people who don't use RPE. Each word is stored as one RPE number, so the
// estimated-max maths (reps left = 10 - RPE) keeps working; an exact RPE is still possible.

export const EFFORTS = [
  { level: 1, label: 'Moderate', rpe: 7, means: '3 or more reps left' },
  { level: 2, label: 'Hard', rpe: 8.5, means: '1 or 2 reps left' },
  { level: 3, label: 'All out', rpe: 10, means: 'nothing left' },
] as const

/** 1 (Moderate) for RPE up to 7.5, 2 (Hard) for 8 to 9, 3 (All out) from 9.5; 0 without RPE. */
export function effortLevel(rpe: number | null | undefined): 0 | 1 | 2 | 3 {
  if (rpe == null) return 0
  if (rpe < 8) return 1
  if (rpe < 9.5) return 2
  return 3
}
