// A small line chart drawn as SVG: one value per session, record sessions marked in the accent.
// Hand-drawn instead of a chart library, which would cost more than the rest of the app.

import { niceScale } from '@/lib/chart'

export type ChartPoint = { value: number; tick: string; record: boolean }

const W = 340
const H = 200
const LEFT = 34
const RIGHT = 8
const TOP = 10
const BOTTOM = 24

export default function LineChart({ points, label }: { points: ChartPoint[]; label: string }) {
  if (points.length === 0) return null
  const values = points.map((p) => p.value)
  const { lo, hi, step } = niceScale(Math.min(...values), Math.max(...values))
  const x = (i: number) =>
    points.length === 1 ? LEFT + (W - LEFT - RIGHT) / 2 : LEFT + (i * (W - LEFT - RIGHT)) / (points.length - 1)
  const y = (v: number) => TOP + ((hi - v) / (hi - lo || 1)) * (H - TOP - BOTTOM)
  const grid: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) grid.push(Math.round(v * 100) / 100)

  // Label at most 4 dates so they never overlap.
  const every = Math.max(1, Math.ceil(points.length / 4))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="block w-full">
      {grid.map((v) => (
        <g key={v}>
          <line x1={LEFT} x2={W - RIGHT} y1={y(v)} y2={y(v)} className="stroke-border" strokeWidth={1} />
          <text x={LEFT - 6} y={y(v) + 3} textAnchor="end" className="fill-faint-foreground font-mono text-[10px]">
            {v}
          </text>
        </g>
      ))}
      <polyline
        points={points.map((p, i) => `${x(i)},${y(p.value)}`).join(' ')}
        fill="none"
        className="stroke-foreground"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(p.value)}
          r={p.record ? 5.5 : 3.5}
          className={`stroke-card ${p.record ? 'fill-accent' : 'fill-foreground'}`}
          strokeWidth={2}
        />
      ))}
      {points.map((p, i) =>
        i % every === 0 || i === points.length - 1 ? (
          <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="fill-faint-foreground font-mono text-[10px]">
            {p.tick}
          </text>
        ) : null,
      )}
    </svg>
  )
}
