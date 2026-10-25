import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { type InputHTMLAttributes, type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import CustomExerciseSheet from '@/components/CustomExerciseSheet'
import { MenuGroup, MenuItem } from '@/components/Menu'
import { api } from '@/lib/api'
import { exerciseSearch } from '@/lib/exerciseSearch'
import type { ExercisesOut } from '@/lib/types'

const TAG = { library: undefined, custom: 'Custom', unrecognized: 'Unrecognized' }

/** An exercise name box: as you type, a list under it searches the library and your own
 *  exercises; "Custom" opens the sheet to add one. The same box in sessions and workout plans;
 *  each passes its own box styling. The keyboard's Enter picks the top row, never the typed text. */
export default function ExercisePicker({ value, onPick, onChange, onFocus, onBlur, onKeyDown, ...input }: InputHTMLAttributes<HTMLInputElement> & {
  value: string
  onPick: (name: string) => void
}) {
  const exercises = useQuery({ queryKey: ['exercises'], queryFn: () => api<ExercisesOut>('/exercises') })
  const search = useMemo(() => exercises.data && exerciseSearch(exercises.data), [exercises.data])
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState<string | null>(null)
  const box = useRef<HTMLInputElement>(null)
  const room = useListRoom(box, open)
  const typed = value.trim()
  const { results, canAdd } = typed && search ? search(typed) : { results: [], canAdd: !!typed }
  const pick = (name: string) => { onPick(name); setOpen(false) }
  const addCustom = () => { setCustom(typed); setOpen(false) }
  return (
    <>
      <input {...input} ref={box} value={value} autoComplete="off" autoCapitalize="words" enterKeyHint="done" placeholder="Exercise name"
        role="combobox" aria-expanded={open && !!typed} className={`scroll-mt-20 ${input.className ?? ''}`}
        onChange={(e) => { setOpen(true); onChange?.(e) }}
        onFocus={(e) => { setOpen(true); onFocus?.(e) }}
        // Opening the sheet takes focus from the box; that isn't the person leaving it.
        onBlur={(e) => custom == null && onBlur?.(e)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && typed) {
            e.preventDefault()
            if (results[0]) pick(results[0].name)
            else if (canAdd) addCustom()
            return
          }
          onKeyDown?.(e)
        }} />
      {open && typed && (
        // Pressing a row would take focus from the box, which commits the typed text first.
        <div onMouseDown={(e) => e.preventDefault()} style={{ maxHeight: room }} className="max-h-72 overflow-y-auto overscroll-contain rounded-2xl">
          <MenuGroup>
            {results.map((r, i) => (
              <MenuItem key={`${r.kind}-${r.name}`} label={r.name} detail={r.matched && `Matches "${r.matched}"`} aside={TAG[r.kind]}
                active={i === 0} onClick={() => pick(r.name)} />
            ))}
            {canAdd && <MenuItem icon={Plus} label="Custom" detail={typed} active={!results.length} onClick={addCustom} />}
          </MenuGroup>
        </div>
      )}
      <CustomExerciseSheet name={custom} onClose={() => setCustom(null)} onSaved={(name) => { setCustom(null); onPick(name) }} />
    </>
  )
}

/** A phone's keyboard covers the page instead of shrinking it, so the list would sit behind it.
 *  While the list is open, the box moves to the top of the screen and the list's height is the
 *  room left between the box and the keyboard. */
function useListRoom(box: RefObject<HTMLInputElement | null>, open: boolean) {
  const [room, setRoom] = useState<number>()
  useEffect(() => {
    const view = window.visualViewport
    if (!open || !view) return
    const fit = () => {
      const bottom = box.current?.getBoundingClientRect().bottom
      if (bottom != null) setRoom(Math.max(160, view.offsetTop + view.height - bottom - 12))
    }
    // After the keyboard has slid up, so the browser's own scrolling has settled.
    const lift = setTimeout(() => box.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 300)
    fit()
    view.addEventListener('resize', fit)
    view.addEventListener('scroll', fit)
    window.addEventListener('scroll', fit)
    return () => {
      clearTimeout(lift)
      view.removeEventListener('resize', fit)
      view.removeEventListener('scroll', fit)
      window.removeEventListener('scroll', fit)
    }
  }, [box, open])
  return room
}
