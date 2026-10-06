import { useState } from 'react'
import BottomBar from '@/components/BottomBar'
import ConfirmSheet from '@/components/ConfirmSheet'

/**
 * The bar at the bottom while editing: Cancel throws the draft away (asking first if anything
 * changed); Save writes it. Nothing is saved before Save.
 */
export default function DraftBar({
  dirty,
  busy,
  error,
  onSave,
  onCancel,
}: {
  dirty: boolean
  busy: boolean
  error: string | null
  onSave: () => void
  onCancel: () => void
}) {
  const [asking, setAsking] = useState(false)
  return (
    <>
      <BottomBar error={error}>
        <div className="flex gap-2.5">
          <button type="button" disabled={busy} onClick={() => (dirty ? setAsking(true) : onCancel())}
            className="h-13 rounded-2xl border border-border px-5 font-semibold">
            Cancel
          </button>
          <button type="button" disabled={busy || !dirty} onClick={onSave}
            className="h-13 flex-1 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-40">
            {busy ? 'Saving…' : dirty ? 'Save Changes' : 'No changes'}
          </button>
        </div>
      </BottomBar>
      <ConfirmSheet open={asking} title="Discard your changes?" body="Nothing you changed here will be saved."
        confirmLabel="Discard Changes" onClose={() => setAsking(false)}
        onConfirm={() => { setAsking(false); onCancel() }} />
    </>
  )
}
