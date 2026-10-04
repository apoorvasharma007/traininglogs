import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import PageTitle from '@/components/PageTitle'
import { api, getApiKey, setApiKey } from '@/lib/api'
import type { LiftsOut } from '@/lib/types'

export default function Settings() {
  const queryClient = useQueryClient()
  const [key, setKey] = useState(getApiKey)
  const lifts = useQuery({ queryKey: ['lifts'], queryFn: () => api<LiftsOut>('/progress/lifts') })

  function saveKey(value: string) {
    setKey(value)
    setApiKey(value)
    // Everything loaded with the old key may have failed; load it again with the new one.
    queryClient.invalidateQueries()
  }

  return (
    <div className="flex flex-col gap-5">
      <PageTitle>Settings</PageTitle>

      <section className="flex flex-col gap-2">
        <h2 className="px-1 text-sm font-semibold">Access</h2>
        <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4">
          <label htmlFor="api-key" className="text-[13px] font-semibold">
            API key
          </label>
          <input
            id="api-key"
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => saveKey(e.target.value)}
            className="h-11 rounded-xl border border-border bg-background px-3.5"
          />
          <p className="text-xs text-muted-foreground">Saved on this device only.</p>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between px-1">
          <h2 className="text-sm font-semibold">Key lifts</h2>
          <span className="text-xs text-muted-foreground">Shown first in Progress</span>
        </div>
        <ul className="overflow-hidden rounded-2xl border border-border bg-card">
          {(lifts.data?.key_lifts ?? []).map((l) => (
            <li key={l.name} className="flex min-h-12 items-center border-t border-border px-4 first:border-t-0">
              {l.name}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
