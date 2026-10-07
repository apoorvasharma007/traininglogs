import { Minus, Plus } from 'lucide-react'

/** A number changed with − and + buttons, kept between min and max. */
export default function CountStepper({
  label,
  value,
  onChange,
  min = 0,
  max = 99,
  step = 1,
  format = String,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  format?: (value: number) => string
}) {
  const button =
    'flex size-11 items-center justify-center rounded-xl text-muted-foreground transition active:scale-90 disabled:opacity-30'
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-[15px]">{label}</span>
      <div className="flex items-center gap-1">
        <button type="button" aria-label={`${label}: less`} disabled={value <= min}
          onClick={() => onChange(Math.max(min, value - step))} className={button}>
          <Minus size={18} aria-hidden />
        </button>
        <span aria-live="polite" className="min-w-16 text-center font-mono text-[15px] font-semibold tabular-nums">
          {format(value)}
        </span>
        <button type="button" aria-label={`${label}: more`} disabled={value >= max}
          onClick={() => onChange(Math.min(max, value + step))} className={button}>
          <Plus size={18} aria-hidden />
        </button>
      </div>
    </div>
  )
}
