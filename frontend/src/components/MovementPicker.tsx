import { Plus } from 'lucide-react'
import { MenuGroup, MenuItem } from '@/components/Menu'
import Parts from '@/components/Parts'
import Sheet from '@/components/Sheet'
import type { Movement } from '@/lib/types'
import { SHEET_TITLE } from '@/lib/ui'

/** "Add Warm-up" or "Add Cool-down": a ready-made set of movements, or one of your own. The same
 * sheet in a live session and in the workout editor. */
export default function MovementPicker({ open, title, presets, onPreset, onOwn, onClose }: {
  open: boolean
  /** "Warm-up" or "Cool-down". */
  title: string
  presets: { name: string; movements: Movement[] }[]
  onPreset: (movements: Movement[]) => void
  onOwn: () => void
  onClose: () => void
}) {
  return (
    <Sheet open={open} onClose={onClose} label={`Add ${title}`}>
      <span className={SHEET_TITLE}>Add {title}</span>
      <MenuGroup>
        {presets.map((p) => (
          <MenuItem key={p.name} label={p.name} detail={<Parts items={p.movements.map((m) => m.name)} />}
            onClick={() => { onPreset(p.movements); onClose() }} />
        ))}
      </MenuGroup>
      <MenuGroup>
        <MenuItem icon={Plus} label="Add Your Own" onClick={() => { onOwn(); onClose() }} />
      </MenuGroup>
    </Sheet>
  )
}
