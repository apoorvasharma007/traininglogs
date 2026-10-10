import { GripVertical } from 'lucide-react'
import { Reorder, useDragControls } from 'motion/react'
import { useState, type ReactNode } from 'react'

/**
 * A list you reorder by dragging each row's handle (Motion's Reorder). Rows move live while
 * dragging; `onReorder` gets the new order once, when the drag ends, and only if it changed.
 */
export default function DragList<T>({
  items,
  keyOf,
  label,
  onReorder,
  bare,
  children,
}: {
  items: T[]
  keyOf: (item: T) => string
  label: (item: T) => string
  onReorder: (keys: string[]) => void
  /** No card of its own: it sits inside one (a SectionCard). */
  bare?: boolean
  children: (item: T) => ReactNode
}) {
  const original = items.map(keyOf)
  const [dragging, setDragging] = useState<string[] | null>(null)
  const order = dragging ?? original
  const byKey = new Map(items.map((i) => [keyOf(i), i]))

  function finish() {
    if (dragging && dragging.join() !== original.join()) onReorder(dragging)
    setDragging(null)
  }

  return (
    <Reorder.Group axis="y" values={order} onReorder={setDragging} className={bare ? '' : 'overflow-hidden rounded-2xl border border-border bg-card'}>
      {order.map((key) => {
        const item = byKey.get(key)
        return item ? (
          <Row key={key} value={key} label={label(item)} onDragEnd={finish}>
            {children(item)}
          </Row>
        ) : null
      })}
    </Reorder.Group>
  )
}

function Row({ value, label, onDragEnd, children }: { value: string; label: string; onDragEnd: () => void; children: ReactNode }) {
  const controls = useDragControls()
  return (
    <Reorder.Item value={value} dragListener={false} dragControls={controls} onDragEnd={onDragEnd}
      className="relative flex items-center border-t border-border/60 bg-card first:border-t-0"
      whileDrag={{ scale: 1.02, boxShadow: '0 8px 24px rgba(0,0,0,0.18)', zIndex: 1 }}>
      <div className="min-w-0 flex-1">{children}</div>
      <button type="button" aria-label={`Drag to reorder ${label}`}
        onPointerDown={(e) => controls.start(e)}
        className="flex h-14 w-11 shrink-0 touch-none items-center justify-center text-faint-foreground">
        <GripVertical size={18} aria-hidden />
      </button>
    </Reorder.Item>
  )
}
