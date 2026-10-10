import { errorText } from '@/lib/errors'


/** What a screen shows while its data loads: grey cards where the content will be, pulsing. */
export function Loading() {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-2.5">
      {[64, 112, 64].map((h, i) => (
        <div key={i} style={{ height: h }} className="animate-pulse rounded-2xl bg-muted" />
      ))}
    </div>
  )
}

export function LoadError({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 text-sm">
      <p className="font-semibold">Couldn't load this</p>
      <p className="text-muted-foreground">{errorText(error)}</p>
      <div className="flex gap-3">
        {retry && (
          <button type="button" onClick={retry} className="font-semibold underline">
            Try Again
          </button>
        )}
      </div>
    </div>
  )
}
