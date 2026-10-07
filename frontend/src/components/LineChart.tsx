// One value per session as a line, record sessions marked in the highlight colour. Recharts,
// loaded only with the screens that use it.
import {
  CartesianGrid,
  Line,
  LineChart as Chart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type DotProps,
} from 'recharts'
import { niceScale } from '@/lib/chart'

// `hollow`: a different measure stood in for this session, drawn as an outline.
type ChartPoint = { value: number; tick: string; record: boolean; hollow?: boolean }

const AXIS = { fontSize: 10, fontFamily: 'var(--font-mono)', fill: 'var(--faint-foreground)' }

function Dot(props: DotProps & { payload?: ChartPoint }) {
  const { cx, cy, payload } = props
  if (cx == null || cy == null) return null
  const record = payload?.record
  if (payload?.hollow) {
    return <circle cx={cx} cy={cy} r={3.5} fill="var(--card)" stroke="var(--foreground)" strokeWidth={1.5} />
  }
  return (
    <circle
      cx={cx}
      cy={cy}
      r={record ? 5.5 : 3.5}
      fill={record ? 'var(--highlight)' : 'var(--foreground)'}
      stroke="var(--card)"
      strokeWidth={2}
    />
  )
}

export default function LineChart({
  points,
  label,
  format,
  hollowLabel,
}: {
  points: ChartPoint[]
  label: string
  format: (value: number) => string
  /** Said after a hollow point's value in the tooltip, e.g. "heaviest". */
  hollowLabel?: string
}) {
  if (points.length === 0) return null
  const values = points.map((p) => p.value)
  const { lo, hi, step } = niceScale(Math.min(...values), Math.max(...values))
  const ticks: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 100) / 100)

  return (
    <div role="img" aria-label={label} className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={points} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="tick" tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
          <YAxis domain={[lo, hi]} ticks={ticks} tick={AXIS} tickLine={false} axisLine={false} width={44} />
          <Tooltip
            cursor={{ stroke: 'var(--border)' }}
            contentStyle={{
              background: 'var(--popover)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              fontSize: 13,
              color: 'var(--popover-foreground)',
            }}
            labelStyle={{ color: 'var(--muted-foreground)' }}
            formatter={(v, _name, item) => [
              item.payload?.hollow && hollowLabel ? `${format(Number(v))} ${hollowLabel}` : format(Number(v)),
              '',
            ]}
            separator=""
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--foreground)"
            strokeWidth={2}
            dot={<Dot />}
            activeDot={{ r: 6, fill: 'var(--foreground)', stroke: 'var(--card)', strokeWidth: 2 }}
            isAnimationActive={!window.matchMedia('(prefers-reduced-motion: reduce)').matches}
          />
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}
