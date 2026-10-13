import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { type InputHTMLAttributes, useMemo, useState } from 'react'
import CustomExerciseSheet from '@/components/CustomExerciseSheet'
import { MenuGroup, MenuItem } from '@/components/Menu'
import { api } from '@/lib/api'
import { exerciseSearch } from '@/lib/exerciseSearch'
import type { ExercisesOut } from '@/lib/types'

const TAG = { library: undefined, custom: 'Custom', unrecognized: 'Unrecognized' }

/** An exercise name box: as you type, a list under it searches the library and your own
 *  exercises; "Custom" opens the sheet to add one. The same box in sessions and workout plans;
 *  each passes its own box styling. */
export default function ExercisePicker({ value, onPick, onChange, onFocus, onBlur, ...input }: InputHTMLAttributes<HTMLInputElement> & {
  value: string
  onPick: (name: string) => void
}) {
  const exercises = useQuery({ queryKey: ['exercises'], queryFn: () => api<ExercisesOut>('/exercises') })
  const search = useMemo(() => exercises.data && exerciseSearch(exercises.data), [exercises.data])
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState<string | null>(null)
  const typed = value.trim()
  const { results, canAdd } = typed && search ? search(typed) : { results: [], canAdd: !!typed }
  return (
    <>
      <input {...input} value={value} autoComplete="off" autoCapitalize="words" placeholder="Exercise name" role="combobox" aria-expanded={open && !!typed}
        onChange={(e) => { setOpen(true); onChange?.(e) }}
        onFocus={(e) => { setOpen(true); onFocus?.(e) }}
        // Opening the sheet takes focus from the box; that isn't the person leaving it.
        onBlur={(e) => custom == null && onBlur?.(e)} />
      {open && typed && (
        // Pressing a row would take focus from the box, which commits the typed text first.
        <div onMouseDown={(e) => e.preventDefault()} className="max-h-72 overflow-y-auto rounded-2xl">
          <MenuGroup>
            {results.map((r) => (
              <MenuItem key={`${r.kind}-${r.name}`} label={r.name} detail={r.matched && `Matches "${r.matched}"`} aside={TAG[r.kind]}
                onClick={() => { onPick(r.name); setOpen(false) }} />
            ))}
            {canAdd && <MenuItem icon={Plus} label="Custom" detail={typed} onClick={() => { setCustom(typed); setOpen(false) }} />}
          </MenuGroup>
        </div>
      )}
      <CustomExerciseSheet name={custom} onClose={() => setCustom(null)} onSaved={(name) => { setCustom(null); onPick(name) }} />
    </>
  )
}
