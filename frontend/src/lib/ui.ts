// The app's buttons, one set for every screen, so the same kind of action always looks the same.
// Main actions are dark, second actions soft grey, destructive ones solid red.

const base = 'font-semibold transition active:scale-[0.98] disabled:opacity-50'

export const BTN = {
  /** The screen's or sheet's main action, full width. */
  primary: `h-13.5 rounded-2xl bg-primary text-base text-primary-foreground ${base}`,
  /** A second choice next to the main one (Keep Going, Cancel). */
  secondary: `h-13.5 rounded-2xl bg-muted text-base text-foreground ${base}`,
  /** Starting something destructive: Remove Set, Delete Program, Discard Session, Sign Out. */
  danger: `h-12 rounded-2xl bg-destructive px-5 text-[15px] text-white ${base}`,
  /** The confirm sheet's button that actually deletes. */
  dangerFill: `h-13.5 rounded-2xl bg-destructive text-base text-white ${base}`,
  /** A small action in a header or a row (Finish, New, Add). */
  smallPrimary: `h-10 rounded-xl bg-primary px-4 text-[15px] text-primary-foreground ${base}`,
  smallSecondary: `h-10 rounded-xl bg-muted px-3.5 text-[15px] text-foreground ${base}`,
  smallDanger: `h-10 rounded-xl bg-destructive px-3.5 text-[15px] text-white ${base}`,
} as const

/** A sheet's title. */
export const SHEET_TITLE = 'text-xl font-bold tracking-tight'
