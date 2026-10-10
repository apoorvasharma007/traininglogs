import { useState } from 'react'
import BottomBar from '@/components/BottomBar'
import ConfirmSheet from '@/components/ConfirmSheet'
import { BTN } from '@/lib/ui'
import { cn } from '@/lib/utils'

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
            className={cn(BTN.secondary, 'px-5')}>
            Cancel
          </button>
          <button type="button" disabled={busy || !dirty} onClick={onSave}
            className={cn(BTN.primary, 'flex-1')}>
            {busy ? 'Saving…' : dirty ? 'Save Changes' : 'No Changes'}
          </button>
        </div>
      </BottomBar>
      <ConfirmSheet open={asking} title="Discard Your Changes?" body="Nothing you changed here will be saved."
        confirmLabel="Discard Changes" onClose={() => setAsking(false)}
        onConfirm={() => { setAsking(false); onCancel() }} />
    </>
  )
}
