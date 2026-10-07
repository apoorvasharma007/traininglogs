import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import ConfirmSheet from '@/components/ConfirmSheet'
import PageTitle from '@/components/PageTitle'
import { api } from '@/lib/api'
import { config, signOut, useSignedIn } from '@/lib/auth'
import { useOutbox } from '@/lib/store'
import type { AiUsage, LiftsOut } from '@/lib/types'

export default function Settings() {
  const email = useSignedIn()
  const unsent = useOutbox().pending.length
  const [signingOut, setSigningOut] = useState(false)
  const lifts = useQuery({ queryKey: ['lifts'], queryFn: () => api<LiftsOut>('/progress/lifts') })
  const aiUsage = useQuery({ queryKey: ['ai-usage'], queryFn: () => api<AiUsage>('/me/ai-usage') })
  const version = useQuery({ queryKey: ['config'], queryFn: config }).data?.version

  return (
    <div className="flex flex-col gap-5">
      <PageTitle>Settings</PageTitle>

      <section className="flex flex-col gap-2">
        <h2 className="px-1 text-sm font-semibold">Access</h2>
        <div className="flex min-h-13 items-center justify-between gap-3 rounded-2xl border border-border bg-card py-1 pr-1 pl-4">
          <span className="min-w-0 truncate text-[15px]">{email}</span>
          <button type="button" onClick={() => setSigningOut(true)} className="h-11 shrink-0 px-3 text-sm font-semibold text-destructive">
            Sign Out
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between px-1">
          <h2 className="text-sm font-semibold">AI Use</h2>
          <span className="text-xs text-muted-foreground">Reading notes and AI fixes</span>
        </div>
        <div className="flex min-h-12 items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4">
          <span>Total So Far</span>
          <span className="tabular-nums">{aiUsage.data && `$${aiUsage.data.total_usd.toFixed(2)}`}</span>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between px-1">
          <h2 className="text-sm font-semibold">Key Lifts</h2>
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

      {version && <p className="text-center text-xs text-muted-foreground">Version {version}</p>}

      <ConfirmSheet
        open={signingOut}
        title="Sign Out?"
        body={
          unsent
            ? `${unsent} ${unsent === 1 ? "session hasn't" : "sessions haven't"} sent yet. ${unsent === 1 ? 'It stays' : 'They stay'} on this phone and ${unsent === 1 ? 'sends' : 'send'} after you sign in again.`
            : 'You can sign in again with a code by email.'
        }
        confirmLabel="Sign Out"
        onClose={() => setSigningOut(false)}
        onConfirm={() => {
          setSigningOut(false)
          signOut()
        }}
      />
    </div>
  )
}
