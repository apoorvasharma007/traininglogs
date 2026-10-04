// Whether a screen is in edit mode with a draft. While it is, the tab bar steps aside, so the
// draft can only be left through Save or Cancel.
import { useEffect, useSyncExternalStore } from 'react'

let editing = false
const listeners = new Set<() => void>()

export function useIsEditing(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => editing,
  )
}

/** Marks the app as editing while `on` is true and the calling screen is shown. */
export function useEditingFlag(on: boolean): void {
  useEffect(() => {
    editing = on
    listeners.forEach((l) => l())
    return () => {
      editing = false
      listeners.forEach((l) => l())
    }
  }, [on])
}
