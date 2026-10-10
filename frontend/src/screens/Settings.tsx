import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState } from 'react'
import ConfirmSheet from '@/components/ConfirmSheet'
import DragList from '@/components/DragList'
import Sheet from '@/components/Sheet'
import { errorText } from '@/lib/errors'
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
  const queryClient = useQueryClient()
  // Saving the list answers with Progress's lifts, so Progress is up to date at once.
  const saveKeyLifts = useMutation({
    mutationFn: (names: string[]) => api<LiftsOut>('/me/key-lifts', { method: 'PUT', body: { names } }),
    onSuccess: (lifts) => queryClient.setQueryData(['lifts'], lifts),
  })
  const [adding, setAdding] = useState(false)
  const keyNames = (lifts.data?.key_lifts ?? []).map((l) => l.name)
  const addable = (lifts.data?.other_lifts ?? []).map((l) => l.name)

  return (
    <div className="flex flex-col gap-5">
      <PageTitle>Settings</PageTitle>

      <section className="flex flex-col gap-2">
        <h2 className="px-1 text-sm font-semibold">Access</h2>
        <div className="flex min-h-13 items-center justify-between gap-3 rounded-2xl border border-border bg-card py-1 pr-1 pl-4">
          <span className="min-w-0 truncate text-[15px]">{email}</span>
          <button type="button" onClick={() => setSigningOut(true)} className="h-11 shrink-0 px-3 text-sm font-semibold text-destructive active:opacity-60">
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
          <span className="tabular-nums">
            {aiUsage.data ? `$${aiUsage.data.total_usd.toFixed(2)}` : aiUsage.isError
              ? <span className="text-sm text-muted-foreground">Couldn't load</span>
              : <span aria-label="Loading" className="inline-block h-4 w-12 animate-pulse rounded bg-muted align-middle" />}
          </span>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between px-1">
          <h2 className="text-sm font-semibold">Key Lifts</h2>
          <span className="text-xs text-muted-foreground">Shown first in Progress</span>
        </div>
        {keyNames.length > 0 && (
          <DragList items={keyNames} keyOf={(n) => n} label={(n) => n} onReorder={(names) => saveKeyLifts.mutate(names)}>
            {(name) => (
              <span className="flex min-h-13 items-center gap-1 pl-4">
                <span className="min-w-0 flex-1 truncate">{name}</span>
                <button type="button" aria-label={`Remove ${name}`} disabled={saveKeyLifts.isPending}
                  onClick={() => saveKeyLifts.mutate(keyNames.filter((n) => n !== name))}
                  className="flex size-11 items-center justify-center text-muted-foreground active:opacity-60">
                  <X size={18} aria-hidden />
                </button>
              </span>
            )}
          </DragList>
        )}
        {saveKeyLifts.isError && <p role="alert" className="px-1 text-sm text-destructive">{errorText(saveKeyLifts.error)}</p>}
        {addable.length > 0 && keyNames.length < 12 && (
          <button type="button" onClick={() => setAdding(true)}
            className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
            + Add Lift
          </button>
        )}
      </section>

      <Sheet open={adding} onClose={() => setAdding(false)} label="Add a Key Lift">
        <span className="text-[17px] font-semibold">Add a Key Lift</span>
        <div className="flex max-h-[60dvh] flex-col overflow-y-auto rounded-2xl border border-border">
          {addable.map((name) => (
            <button key={name} type="button"
              onClick={() => { setAdding(false); saveKeyLifts.mutate([...keyNames, name]) }}
              className="flex min-h-13 items-center border-t border-border px-4 text-left text-[15px] first:border-t-0 active:bg-muted">
              {name}
            </button>
          ))}
        </div>
      </Sheet>

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
