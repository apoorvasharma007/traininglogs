import type { MouseEvent } from 'react'
import { BACK, FRONT } from '@/lib/bodyOutline'
import type { MarkMode } from '@/lib/muscleMarks'

const UNPICKED = 'color-mix(in srgb, var(--muted-foreground) 35%, transparent)'
const SKIN = 'color-mix(in srgb, var(--muted-foreground) 15%, transparent)'
const FILL = {
  primary: 'var(--highlight)',
  secondary: `color-mix(in srgb, var(--highlight) 38%, ${UNPICKED})`,
}
const SIDES = { front: FRONT, back: BACK }
export type BodySide = keyof typeof SIDES

/** One side of the body, as wide as its container. Reports the tapped group (the nearest one when
 *  the tap misses every shape) and the tap's screen point. */
export default function BodyFigure({ side, focus, markOfGroup, onTap }: {
  side: BodySide
  focus: string | null
  markOfGroup: (group: string) => MarkMode | null
  onTap: (tap: { group: string | null; clientX: number; clientY: number }) => void
}) {
  const { box, shapes } = SIDES[side]
  const tap = (e: MouseEvent<SVGSVGElement>) => {
    // The figure's height follows its width, so a tap's place in the element is its place in the drawing.
    const r = e.currentTarget.getBoundingClientRect()
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height
    const [x, y, w, h] = box.split(' ').map(Number)
    let group = (e.target as Element).getAttribute('data-group')
    if (!group) {
      const at = { x: x + fx * w, y: y + fy * h }
      const near = shapes.filter(([g]) => g).map(([g, cx, cy]) => ({ g, d: Math.hypot(cx - at.x, cy - at.y) })).sort((a, b) => a.d - b.d)[0]
      group = near.d < 60 ? near.g : null
    }
    onTap({ group, clientX: e.clientX, clientY: e.clientY })
  }

  return (
    <svg viewBox={box} role="img" aria-label={`${side === 'front' ? 'Front' : 'Back'} of the body`} onClick={tap}
      className="h-auto w-full touch-manipulation">
      {shapes.map(([g, , , path], i) => {
        const mark = g && markOfGroup(g)
        return (
          <path key={i} d={path} data-group={g ?? undefined} stroke={g && g === focus ? 'var(--foreground)' : 'none'} strokeWidth={4}
            fill={!g ? SKIN : mark ? FILL[mark] : UNPICKED} />
        )
      })}
    </svg>
  )
}
