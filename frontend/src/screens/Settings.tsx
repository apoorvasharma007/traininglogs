import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, X } from 'lucide-react'
import { useState } from 'react'
import ConfirmSheet from '@/components/ConfirmSheet'
import DragList from '@/components/DragList'
import FeedbackSheet from '@/components/FeedbackSheet'
import Sheet from '@/components/Sheet'
import { errorText } from '@/lib/errors'
import PageTitle from '@/components/PageTitle'
import { api } from '@/lib/api'
import { config, signOut, useSignedIn } from '@/lib/auth'
import { useOutbox } from '@/lib/store'
import type { AiUsage, LiftsOut } from '@/lib/types'
import { BTN, SHEET_TITLE } from '@/lib/ui'
import { cn } from '@/lib/utils'
import SectionCard from '@/components/SectionCard'
import { MenuGroup, MenuItem } from '@/components/Menu'

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
  const [feedback, setFeedback] = useState(false)
  // The key lift whose × was tapped: removed only after the confirm.
  const [removing, setRemoving] = useState<string | null>(null)
  const keyNames = (lifts.data?.key_lifts ?? []).map((l) => l.name)
  const addable = (lifts.data?.other_lifts ?? []).map((l) => l.name)

  return (
    <div className="flex flex-col gap-5">
      <PageTitle>Settings</PageTitle>

      <SectionCard title="Account">
        <div className="flex min-h-13 items-center justify-between gap-3 py-1 pr-1 pl-4">
          <span className="min-w-0 truncate text-[15px]">{email}</span>
          <button type="button" onClick={() => setSigningOut(true)} className={cn(BTN.smallDanger, 'shrink-0')}>
            Sign Out
          </button>
        </div>
      </SectionCard>

      <SectionCard title="AI Use" aside="Reading notes and AI fixes">
        <div className="flex min-h-12 items-center justify-between gap-3 px-4">
          <span>Total So Far</span>
          <span className="tabular-nums">
            {aiUsage.data ? `$${aiUsage.data.total_usd.toFixed(2)}` : aiUsage.isError
              ? <span className="text-[15px] text-muted-foreground">Couldn't load</span>
              : <span aria-label="Loading" className="inline-block h-4 w-12 animate-pulse rounded bg-muted align-middle" />}
          </span>
        </div>
      </SectionCard>

      <div className="flex flex-col gap-2.5">
        <SectionCard title="Key Lifts" aside="Shown first in Progress">
          {keyNames.length > 0 && (
            <DragList items={keyNames} keyOf={(n) => n} label={(n) => n} onReorder={(names) => saveKeyLifts.mutate(names)} bare>
              {(name) => (
                <span className="flex min-h-13 items-center gap-1 pl-4">
                  <span className="min-w-0 flex-1 truncate">{name}</span>
                  <button type="button" aria-label={`Remove ${name}`} disabled={saveKeyLifts.isPending}
                    onClick={() => setRemoving(name)}
                    className="flex size-11 items-center justify-center text-muted-foreground active:opacity-60">
                    <X size={18} aria-hidden />
                  </button>
                </span>
              )}
            </DragList>
          )}
        </SectionCard>
        {saveKeyLifts.isError && <p role="alert" className="px-1 text-[15px] text-destructive">{errorText(saveKeyLifts.error)}</p>}
        {addable.length > 0 && keyNames.length < 12 && (
          <button type="button" onClick={() => setAdding(true)}
            className={BTN.secondary}>
            + Add Lift
          </button>
        )}
      </div>

      <ConfirmSheet open={removing != null} title={`Remove ${removing ?? 'Lift'}?`}
        body="It leaves your Key Lifts. You can add it back any time."
        confirmLabel="Remove" busy={saveKeyLifts.isPending} busyLabel="Removing…"
        error={saveKeyLifts.isError ? errorText(saveKeyLifts.error) : undefined}
        onClose={() => setRemoving(null)}
        onConfirm={() => saveKeyLifts.mutate(keyNames.filter((n) => n !== removing), { onSuccess: () => setRemoving(null) })} />

      <Sheet open={adding} onClose={() => setAdding(false)} label="Add a Key Lift">
        <span className={SHEET_TITLE}>Add a Key Lift</span>
        <MenuGroup>
          {addable.map((name) => (
            <MenuItem key={name} label={name} onClick={() => { setAdding(false); saveKeyLifts.mutate([...keyNames, name]) }} />
          ))}
        </MenuGroup>
      </Sheet>

      <SectionCard title="Feedback" aside="Ideas and problems">
        <button type="button" onClick={() => setFeedback(true)}
          className="flex min-h-13 w-full items-center justify-between gap-3 px-4 text-left text-[15px] active:bg-muted">
          Send Feedback
          <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
        </button>
      </SectionCard>
      <FeedbackSheet open={feedback} onClose={() => setFeedback(false)} />

      {version && <p className="text-center text-[13px] text-muted-foreground">Version {version}</p>}

      <ConfirmSheet
        open={signingOut}
        title="Sign Out?"
        body={
          unsent
            ? `${unsent} ${unsent === 1 ? "session hasn't" : "sessions haven't"} sent yet. ${unsent === 1 ? 'It stays' : 'They stay'} on this phone and ${unsent === 1 ? 'sends' : 'send'} after you sign in.`
            : 'You can sign back in any time with your email.'
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
