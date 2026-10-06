import type { ReactNode } from 'react'

/** Short pieces of one line ("best 138.7 kg", "9 sessions", or a list of exercise names), kept
 * apart by space instead of a dot, wrapping onto the next line when they don't fit. */
export default function Parts({ items, className = '' }: { items: ReactNode[]; className?: string }) {
  return (
    <span className={`flex flex-wrap gap-x-3 gap-y-0.5 ${className}`}>
      {items.map((item, i) => (
        <span key={i}>{item}</span>
      ))}
    </span>
  )
}
