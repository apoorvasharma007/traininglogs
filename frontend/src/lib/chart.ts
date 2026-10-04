// Axis maths for the hand-drawn charts.

/** Round axis bounds and the step between grid lines, about 4 lines over the data's range. */
export function niceScale(min: number, max: number): { lo: number; hi: number; step: number } {
  const span = max - min || Math.abs(max) || 1
  const raw = span / 4
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag
  return { lo: Math.floor(min / step) * step, hi: Math.ceil(max / step) * step || step, step }
}
