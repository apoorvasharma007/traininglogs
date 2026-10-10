import { type FocusEvent, useRef } from 'react'
import { cn } from '@/lib/utils'

/**
 * A weight or reps box: tap it and the number keypad opens. A grey placeholder is last time's value
 * (or a suggestion); typing replaces it. When `fillable`, the first tap fills the grey number in
 * without the keypad, and the next tap opens the keypad with the number selected.
 */
export default function NumberBox({
  label,
  value,
  placeholder,
  inputMode = 'decimal',
  done,
  flagged,
  fillable,
  className,
  onChange,
  onBlur,
}: {
  label: string
  value: string
  placeholder: string
  inputMode?: 'decimal' | 'numeric' | 'text'
  done?: boolean
  /** The AI wasn't sure of this value: an amber outline until it's looked at. */
  flagged?: boolean
  /** The placeholder is a value worth taking as it is. */
  fillable?: boolean
  className?: string
  onChange: (value: string) => void
  /** Typing is over: the box lost focus (not counting a tap-to-fill). */
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void
}) {
  const fill = Boolean(fillable && value === '' && placeholder)
  const filling = useRef(false)
  return (
    <input
      aria-label={label}
      inputMode={inputMode}
      enterKeyHint="done"
      autoComplete="off"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value.replace(',', '.'))}
      onBlur={(e) => { if (!filling.current) onBlur?.(e) }}
      // Read-only until filled, so the first tap doesn't bring up the keypad.
      readOnly={fill}
      onClick={fill ? (e) => {
        filling.current = true
        onChange(placeholder)
        e.currentTarget.blur()
        filling.current = false
      } : undefined}
      onFocus={(e) => e.target.select()}
      onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
      data-check={flagged ? '' : undefined}
      className={cn(
        'h-10 w-full min-w-0 rounded-lg border border-transparent text-center font-mono text-[15px] tabular-nums transition-colors',
        'placeholder:text-faint-foreground focus:border-ring focus:bg-card focus:outline-none',
        done ? 'bg-transparent' : 'bg-muted',
        // Last, so it wins over the plain transparent border.
        flagged && 'border-warning',
        className,
      )}
    />
  )
}
