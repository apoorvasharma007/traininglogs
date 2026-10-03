import { Link } from 'wouter'
import { ApiError } from '@/lib/api'

/** What a screen shows while its data loads or when the request fails. */
export function Loading() {
  return (
    <div role="status" className="py-10 text-center text-sm text-muted-foreground">
      Loading…
    </div>
  )
}

export function LoadError({ error, retry }: { error: unknown; retry?: () => void }) {
  const noKey = error instanceof ApiError && error.status === 401
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 text-sm">
      <p className="font-semibold">Couldn't load this</p>
      <p className="text-muted-foreground">{error instanceof Error ? error.message : String(error)}</p>
      <div className="flex gap-3">
        {noKey && (
          <Link href="/settings" className="font-semibold underline">
            Open Settings
          </Link>
        )}
        {retry && (
          <button type="button" onClick={retry} className="font-semibold underline">
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
