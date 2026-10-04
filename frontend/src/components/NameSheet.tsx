import { useState } from 'react'
import Sheet from '@/components/Sheet'

/** A sheet asking for one name: a new program, a rename. Save is off while the name is blank. */
export default function NameSheet({
  open,
  title,
  label,
  initial = '',
  placeholder,
  saveLabel = 'Save',
  busy,
  error,
  allowBlank = false,
  onSave,
  onClose,
}: {
  open: boolean
  title: string
  label: string
  initial?: string
  placeholder?: string
  saveLabel?: string
  busy?: boolean
  error?: string | null
  allowBlank?: boolean
  onSave: (name: string) => void
  onClose: () => void
}) {
  return (
    <Sheet open={open} onClose={onClose} label={title}>
      {open && (
        <NameForm title={title} label={label} initial={initial} placeholder={placeholder} saveLabel={saveLabel}
          busy={busy} error={error} allowBlank={allowBlank} onSave={onSave} />
      )}
    </Sheet>
  )
}

function NameForm(props: {
  title: string
  label: string
  initial: string
  placeholder?: string
  saveLabel: string
  busy?: boolean
  error?: string | null
  allowBlank: boolean
  onSave: (name: string) => void
}) {
  const [name, setName] = useState(props.initial)
  const blocked = props.busy || (!props.allowBlank && !name.trim())
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (!blocked) props.onSave(name.trim())
      }}
    >
      <span className="text-[17px] font-semibold">{props.title}</span>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="name-input" className="text-[13px] font-semibold">
          {props.label}
        </label>
        <input id="name-input" autoFocus value={name} placeholder={props.placeholder}
          onChange={(e) => setName(e.target.value)}
          className="h-12 rounded-xl border border-border bg-background px-3.5 text-[15px]" />
      </div>
      {props.error && <p role="alert" className="text-sm text-destructive">{props.error}</p>}
      <button type="submit" disabled={blocked}
        className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-50">
        {props.busy ? 'Saving…' : props.saveLabel}
      </button>
    </form>
  )
}
