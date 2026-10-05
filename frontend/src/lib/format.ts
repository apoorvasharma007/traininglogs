// Small display helpers shared by the screens.
import type { WorkingSet } from '@/lib/types'

const DAY = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const SHORT = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })

// API dates are "2026-10-02". Parsed as local dates so the day never shifts with the time zone.
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** "Fri 2 Oct" */
export function dayLabel(iso: string): string {
  return DAY.format(parseDate(iso))
}

/** "2 Oct" */
export function shortDate(iso: string): string {
  return SHORT.format(parseDate(iso))
}

/** 125 -> "125", 47.5 -> "47.5", 133.33 -> "133.3" */
export function kg(value: number): string {
  return String(Math.round(value * 10) / 10)
}

/** Monday of the week a date falls in, as a local date. */
function weekStart(d: Date): Date {
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7))
  return start
}

/** Groups items by calendar week (Monday first), newest week first, keeping their order. */
export function groupByWeek<T>(items: T[], dateOf: (item: T) => string, today: Date) {
  const thisWeek = weekStart(today).getTime()
  const groups: { title: string; items: T[] }[] = []
  let current: number | null = null
  for (const item of items) {
    const start = weekStart(parseDate(dateOf(item)))
    if (start.getTime() !== current) {
      current = start.getTime()
      const end = new Date(start)
      end.setDate(end.getDate() + 6)
      const title =
        current === thisWeek ? 'This week' : `${SHORT.format(start)} to ${SHORT.format(end)}`
      groups.push({ title, items: [] })
    }
    groups[groups.length - 1].items.push(item)
  }
  return groups
}

/**
 * What History calls a session: its workout's name, or a name it was given; otherwise its first
 * exercises ("Squat · Bench press · Pull ups"). Older sessions keep the name their note gave them.
 */
export function sessionName(s: { focus: string | null; exercises: (string | { name: string })[] }): string {
  if (s.focus?.trim()) return s.focus.trim()
  const names = s.exercises.map((e) => (typeof e === 'string' ? e : e.name))
  return names.length ? names.slice(0, 3).join(' · ') + (names.length > 3 ? ' …' : '') : 'Session'
}

/** "8", "8+1" with partial reps, "8L / 7R" for one side at a time. */
export function repsText(s: WorkingSet): string {
  if (s.reps_full != null) return s.reps_partial ? `${s.reps_full}+${s.reps_partial}` : String(s.reps_full)
  if (s.left_reps_full != null || s.right_reps_full != null) {
    return `${s.left_reps_full ?? '?'}L / ${s.right_reps_full ?? '?'}R`
  }
  return '–'
}
