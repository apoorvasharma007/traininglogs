import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Collapse } from '@/components/Collapse'
import { MenuGroup, MenuItem } from '@/components/Menu'
import Sheet from '@/components/Sheet'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { EQUIPMENT, JOINTS, LOGS, MOVEMENT_PATTERNS, MUSCLE_GROUPS } from '@/lib/lists'
import { BTN, SHEET_TITLE } from '@/lib/ui'

const BOX = 'h-12 rounded-xl border border-border bg-background px-3.5 text-[15px]'
const title = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase()).replace('Ez ', 'EZ ')
const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])
// Each option of a flat list is a group of one, which picks directly.
const flat = (list: string[]): [string, string[]][] => list.map((v) => [title(v), [v]])
const JOINT_GROUPS: [string, string[]][] = JOINTS.map(([joint, moves]) => [joint, moves.map((m) => `${joint.toLowerCase()} ${m}`)])

const blank = (name: string) => ({
  name, primary: [] as string[], log: 'Weight and Reps', equipment: null as string | null, equipmentOther: '',
  secondary: [] as string[], compound: null as boolean | null, joints: [] as string[], patterns: [] as string[],
})

/** A new custom exercise: a name and its primary muscles, then optional details
 *  (exercise-library-plan.md, section 9). Open while `name` is set; it starts as the typed text. */
export default function CustomExerciseSheet({ name, onSaved, onClose }: {
  name: string | null
  onSaved: (name: string) => void
  onClose: () => void
}) {
  const [form, setForm] = useState(() => blank(''))
  const [row, setRow] = useState<string | null>('primary')
  // Each opening starts fresh with the typed name.
  const [openedFor, setOpenedFor] = useState<string | null>(null)
  if (name !== openedFor) {
    setOpenedFor(name)
    if (name != null) { setForm(blank(name)); setRow('primary') }
  }
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }))
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: () => api('/exercises', {
      method: 'POST',
      body: {
        name: form.name, measures: LOGS.find(([l]) => l === form.log)![1], primary_muscles: form.primary,
        secondary_muscles: form.secondary, equipment: form.equipment, equipment_other: form.equipmentOther || null,
        compound: form.compound, joint_actions: form.joints, movement_patterns: form.patterns,
      },
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['exercises'] }); onSaved(form.name.trim()) },
  })
  const why = !form.name.trim() ? 'Add a name to save' : form.primary.length === 0 ? 'Choose a primary muscle to save' : null

  /** A row that opens on tap, one at a time, its value on the right. */
  const section = (id: string, label: string, value: string | null, body: ReactNode, opts: { detail?: string; required?: boolean } = {}) => (
    <>
      <MenuItem label={label} detail={opts.detail} onClick={() => setRow(row === id ? null : id)}
        aside={value ? <span className="block max-w-40 truncate text-highlight">{value}</span> : opts.required ? 'Required' : 'Add'} />
      <Collapse open={row === id}>
        <div className="flex flex-col gap-2 px-3 pb-3">{body}</div>
      </Collapse>
    </>
  )
  const list = (values: string[]) => values.map(title).join(', ') || null

  return (
    <Sheet open={name != null} onClose={onClose} label="Custom Exercise"
      footer={
        <>
          {(why || save.error) && (
            <p role={why ? undefined : 'alert'} className={`text-center text-[13px] ${why ? 'text-muted-foreground' : 'text-destructive'}`}>
              {why ?? errorText(save.error)}
            </p>
          )}
          <button type="button" disabled={!!why || save.isPending} onClick={() => save.mutate()} className={BTN.primary}>
            Save
          </button>
        </>
      }>
      <span className={SHEET_TITLE}>Custom Exercise</span>
      <input aria-label="Exercise name" placeholder="Exercise name" autoCapitalize="words" value={form.name}
        onChange={(e) => set({ name: e.target.value })} className={BOX} />
      <MenuGroup>
        {section('primary', 'Primary Muscles', list(form.primary),
          <Tiles groups={MUSCLE_GROUPS} picked={form.primary} onPick={(v) => set({ primary: toggle(form.primary, v) })} />,
          { detail: '+1 Per Set', required: true })}
        {section('log', 'Log', form.log,
          <Tiles groups={flat(LOGS.map(([l]) => l))} picked={[form.log]} onPick={(log) => { set({ log }); setRow(null) }} />)}
      </MenuGroup>
      <span className="-mb-2 text-[13px] font-semibold">Optional</span>
      <MenuGroup>
        {section('equipment', 'Equipment', form.equipment === 'other' ? form.equipmentOther || 'Other' : form.equipment && title(form.equipment),
          <>
            <Tiles groups={flat(EQUIPMENT)} picked={form.equipment ? [form.equipment] : []}
              onPick={(equipment) => { set({ equipment }); if (equipment !== 'other') setRow(null) }} />
            {form.equipment === 'other' && (
              <input aria-label="What equipment" placeholder="What is it?" value={form.equipmentOther}
                onChange={(e) => set({ equipmentOther: e.target.value })} className={BOX} />
            )}
          </>)}
        {section('secondary', 'Secondary Muscles', list(form.secondary),
          <Tiles groups={MUSCLE_GROUPS} picked={form.secondary} onPick={(v) => set({ secondary: toggle(form.secondary, v) })} />,
          { detail: '+0.5 Per Set' })}
        {section('compound', 'Compound', form.compound == null ? null : form.compound ? 'Compound' : 'Isolation',
          <div role="group" aria-label="Compound" className="grid grid-cols-2 gap-1 rounded-2xl bg-card p-1">
            {[true, false].map((c) => (
              <button key={String(c)} type="button" aria-pressed={form.compound === c} onClick={() => { set({ compound: c }); setRow(null) }}
                className={`h-11 rounded-xl text-[15px] font-semibold ${form.compound === c ? 'bg-muted text-foreground shadow-sm' : 'text-muted-foreground'}`}>
                {c ? 'Compound' : 'Isolation'}
              </button>
            ))}
          </div>)}
        {section('joints', 'Joint Movements', list(form.joints),
          <Tiles groups={JOINT_GROUPS} picked={form.joints} label={(v, joint) => title(v.slice(joint.length + 1))}
            onPick={(v) => set({ joints: toggle(form.joints, v) })} />)}
        {section('patterns', 'Movement Patterns', list(form.patterns),
          <Tiles groups={flat(MOVEMENT_PATTERNS)} picked={form.patterns} onPick={(v) => set({ patterns: toggle(form.patterns, v) })} />)}
      </MenuGroup>
    </Sheet>
  )
}

/** A 3-column grid of groups. A group of several opens to its options, showing how many are
 *  picked ("Shoulders 1/4"); picking one goes back to the groups. A group of one picks directly. */
function Tiles({ groups, picked, label = title, onPick }: {
  groups: [string, string[]][]
  picked: string[]
  label?: (value: string, group: string) => string
  onPick: (value: string) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const tile = (on: boolean) => `min-h-12 rounded-xl px-2 py-1.5 text-center text-sm font-semibold ${
    on ? 'bg-highlight-soft text-highlight' : 'bg-card text-foreground'}`
  const options = groups.find(([g]) => g === open)?.[1]
  if (open && options) {
    return (
      <>
        <button type="button" onClick={() => setOpen(null)} className="flex items-center gap-1 self-start text-sm font-semibold text-muted-foreground">
          <ChevronLeft size={16} aria-hidden />
          {open}
        </button>
        <div className="grid grid-cols-2 gap-1.5">
          {options.map((v) => (
            <button key={v} type="button" aria-pressed={picked.includes(v)} onClick={() => { onPick(v); setOpen(null) }} className={tile(picked.includes(v))}>
              {label(v, open)}
            </button>
          ))}
        </div>
      </>
    )
  }
  return (
    <div className="grid grid-cols-3 gap-1.5">
      {groups.map(([g, values]) => {
        const n = values.filter((v) => picked.includes(v)).length
        return (
          <button key={g} type="button" aria-pressed={n > 0} onClick={() => (values.length > 1 ? setOpen(g) : onPick(values[0]))} className={tile(n > 0)}>
            {g}
            {values.length > 1 && (
              <span className="ml-1 font-mono text-xs whitespace-nowrap">
                {n ? `${n}/${values.length}` : values.length}
                <ChevronRight size={12} aria-hidden className="inline" />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
