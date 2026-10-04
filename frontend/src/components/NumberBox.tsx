import { cn } from '@/lib/utils'

/**
 * A weight or reps box on a set row: tap it and the number keypad opens. A grey placeholder is
 * last time's value; typing replaces it.
 */
export default function NumberBox({
  label,
  value,
  placeholder,
  inputMode = 'decimal',
  done,
  onChange,
  onBlur,
}: {
  label: string
  value: string
  placeholder: string
  inputMode?: 'decimal' | 'numeric' | 'text'
  done?: boolean
  onChange: (value: string) => void
  onBlur?: () => void
}) {
  return (
    <input
      aria-label={label}
      inputMode={inputMode}
      enterKeyHint="done"
      autoComplete="off"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value.replace(',', '.'))}
      onBlur={onBlur}
      onFocus={(e) => e.target.select()}
      onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
      className={cn(
        'h-10 w-full min-w-0 rounded-lg border border-transparent text-center font-mono text-[15px] tabular-nums transition-colors',
        'placeholder:text-faint-foreground focus:border-ring focus:bg-card focus:outline-none',
        done ? 'bg-transparent' : 'bg-muted',
      )}
    />
  )
}
