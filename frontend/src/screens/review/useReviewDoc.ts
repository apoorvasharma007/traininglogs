import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/lib/api'
import type { Card, CardEdit, CardOp, EditReply } from '@/lib/types'

/** The review being edited: the extract to round-trip to the API, and the card to show. */
type Doc = { extract: Record<string, unknown> | null; card: Card }

type Step = { edits: CardEdit[] } | { op: CardOp } | { instruction: string }

/**
 * Holds a pending extraction while it's reviewed. The server keeps no draft: every change sends
 * the current extract and gets the new one back, so undo is just putting the previous one back.
 */
export function useReviewDoc(extractionId: string) {
  const initial = useQuery({
    queryKey: ['extraction', extractionId],
    queryFn: () => api<Card>(`/extractions/${extractionId}`),
    staleTime: Infinity,
  })
  const [doc, setDoc] = useState<Doc | null>(null)
  const [corrections, setCorrections] = useState<Record<string, unknown>[]>([])
  const [undoState, setUndoState] = useState<{ doc: Doc; corrections: Record<string, unknown>[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A failed AI fix shows its error in the fix box, next to the message, not in the floating bar.
  const [errorFromFix, setErrorFromFix] = useState(false)

  const current: Doc | null = doc ?? (initial.data ? { extract: null, card: initial.data } : null)

  /** One request on top of `base`. `instruction` goes to /correct (AI), the rest to /edit. */
  async function send(base: Doc, step: Step): Promise<{ doc: Doc; correction: Record<string, unknown>; created: string | null }> {
    const extract = base.extract ?? undefined
    const reply =
      'instruction' in step
        ? await api<EditReply>(`/extractions/${extractionId}/correct`, {
            method: 'POST',
            body: { extract, instruction: step.instruction },
          })
        : await api<EditReply>(`/extractions/${extractionId}/edit`, { method: 'POST', body: { extract, ...step } })
    return { doc: { extract: reply.extract, card: reply.card }, correction: reply.correction, created: reply.created_path }
  }

  /**
   * Runs steps in order, each on the result of the one before, and keeps the result only if all
   * succeed. A step may be a function that builds it from the previous step's created path.
   * Returns the new doc and the last created path, or undefined when something failed (the
   * error is then in `error`).
   */
  async function run(
    steps: (Step | ((created: string | null, doc: Doc) => Step | null))[],
    options?: { undoable?: boolean },
  ): Promise<{ doc: Doc; created: string | null; corrections: Record<string, unknown>[] } | undefined> {
    if (!current) return undefined
    setBusy(true)
    setError(null)
    let working = current
    let created: string | null = null
    const added: Record<string, unknown>[] = []
    try {
      for (const s of steps) {
        const step = typeof s === 'function' ? s(created, working) : s
        if (!step) continue
        const result = await send(working, step)
        working = result.doc
        created = result.created ?? created
        added.push(result.correction)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setErrorFromFix(steps.some((s) => typeof s !== 'function' && 'instruction' in s))
      setBusy(false)
      return undefined
    }
    const all = [...corrections, ...added]
    setUndoState(options?.undoable ? { doc: current, corrections } : null)
    setDoc(working)
    setCorrections(all)
    setBusy(false)
    return { doc: working, created, corrections: all }
  }

  function undo() {
    if (!undoState) return
    setDoc(undoState.doc)
    setCorrections(undoState.corrections)
    setUndoState(null)
  }

  return {
    initial,
    doc: current,
    corrections,
    busy,
    error,
    errorFromFix,
    clearError: () => setError(null),
    run,
    canUndo: undoState != null,
    undo,
    dismissUndo: () => setUndoState(null),
  }
}
