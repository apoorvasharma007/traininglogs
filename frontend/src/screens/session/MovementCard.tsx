import { Check, Plus } from 'lucide-react'
import { useState } from 'react'
import { newMovement, type LiveMovement } from '@/lib/session'
import type { Movement } from '@/lib/types'
import MovementPicker from '@/components/MovementPicker'

/**
 * The session's warm-up or cool-down: a slim "+ Warm-up" line while empty, otherwise one row per
 * movement (name, amount, tick). Unticked movements are left out at Finish.
 */
export default function MovementCard({
  title,
  movements,
  presets,
  onChange,
  onAddPreset,
}: {
  /** "Warm-up" or "Cool-down"; the drawer's heading adds "templates". */
  title: string
  movements: LiveMovement[]
  presets: { name: string; movements: Movement[] }[]
  onChange: (list: LiveMovement[]) => void
  onAddPreset: (movements: Movement[]) => void
}) {
  const [choosing, setChoosing] = useState(false)
  const update = (key: string, patch: Partial<LiveMovement>) =>
    onChange(movements.map((m) => (m.key === key ? { ...m, ...patch } : m)))

  const picker = (
    <MovementPicker open={choosing} title={title} presets={presets} onClose={() => setChoosing(false)}
      onPreset={onAddPreset} onOwn={() => onChange([...movements, newMovement()])} />
  )

  if (movements.length === 0) {
    return (
      <>
        <button type="button" onClick={() => setChoosing(true)}
          className="flex h-10 items-center gap-1.5 self-start rounded-xl px-2 text-[13px] font-semibold text-muted-foreground">
          <Plus size={14} aria-hidden /> {title}
        </button>
        {picker}
      </>
    )
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between py-1 pr-1 pl-4">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        <button type="button" aria-label={`Add to ${title.toLowerCase()}`} onClick={() => setChoosing(true)}
          className="flex size-10 items-center justify-center text-muted-foreground">
          <Plus size={18} aria-hidden />
        </button>
      </div>
      {movements.map((m) => (
        <div key={m.key} className={`grid min-h-12 grid-cols-[minmax(0,1fr)_88px_48px] items-center gap-1.5 pl-4 ${m.done ? 'bg-highlight-soft' : ''}`}>
          <input aria-label="Movement" value={m.name} placeholder="Movement" onChange={(e) => update(m.key, { name: e.target.value })}
            className="h-10 min-w-0 bg-transparent text-[15px] placeholder:text-faint-foreground focus:outline-none" />
          <input aria-label={`Amount for ${m.name || 'movement'}`} value={m.amount} placeholder="10 or 3 min"
            onChange={(e) => update(m.key, { amount: e.target.value })}
            className="h-10 w-full rounded-lg bg-muted text-center font-mono text-[13px] placeholder:font-sans placeholder:text-[11px] placeholder:text-faint-foreground" />
          <button type="button" onClick={() => update(m.key, { done: !m.done })} aria-label={`${m.name || 'Movement'} done`} aria-pressed={m.done}
            className="flex size-12 items-center justify-center">
            <span className={`flex size-7 items-center justify-center rounded-lg border-[1.5px] ${m.done ? 'border-highlight bg-highlight text-background' : 'border-border text-transparent'}`}>
              <Check size={18} strokeWidth={3} aria-hidden />
            </span>
          </button>
        </div>
      ))}
      {picker}
    </section>
  )
}
