/** The screen's name as a field in the header while editing; part of the draft until Save. */
export default function HeaderName({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string
  value: string
  placeholder: string
  onChange: (value: string) => void
}) {
  return (
    <>
      <label htmlFor="header-name" className="sr-only">
        {label}
      </label>
      <input
        id="header-name"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-card px-3 text-[17px] font-semibold"
      />
    </>
  )
}

/** "Edit", shown while viewing. */
export function EditButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="h-11 shrink-0 px-3 text-[15px] font-semibold">
      Edit
    </button>
  )
}
