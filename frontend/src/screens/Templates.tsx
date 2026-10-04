import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { planText, useCopyTemplate, useTemplates } from '@/lib/programs'
import type { ProgramTemplate } from '@/lib/types'

/** Ready-made programs. Tapping one shows its workouts; "Add program" copies it into yours. */
export default function Templates() {
  const templates = useTemplates()
  const copy = useCopyTemplate()
  const [, navigate] = useLocation()
  const [open, setOpen] = useState<ProgramTemplate | null>(null)

  return (
    <div className="flex flex-col">
      <ScreenHeader back="/programs" backLabel="Back to Programs" title="Templates" />
      {templates.isPending && <Loading />}
      {templates.isError && <LoadError error={templates.error} retry={() => templates.refetch()} />}
      {templates.data && (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          {templates.data.map((t) => (
            <button key={t.id} type="button" onClick={() => { copy.reset(); setOpen(t) }}
              className="flex min-h-16 w-full items-center gap-2.5 border-t border-border px-4 py-2 text-left first:border-t-0 active:bg-muted">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-[15px] font-semibold">{t.name}</span>
                <span className="text-xs text-muted-foreground">{t.days}</span>
              </span>
              <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
            </button>
          ))}
        </div>
      )}

      <Sheet open={open != null} onClose={() => setOpen(null)} label={open?.name ?? 'Template'}>
        {open && (
          <>
            <span className="text-[17px] font-semibold">{open.name}</span>
            <div className="flex max-h-[55dvh] flex-col gap-3 overflow-y-auto">
              {open.workouts.map((w) => (
                <section key={w.name}>
                  <h2 className="mb-1 text-[13px] font-semibold text-muted-foreground">{w.name}</h2>
                  <ul>
                    {w.exercises.map((e) => (
                      <li key={e.name} className="flex min-h-8 items-center justify-between gap-3 border-t border-border text-sm">
                        <span className="truncate">{e.name}</span>
                        <span className="shrink-0 font-mono text-xs text-muted-foreground">{planText(e)}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
            {copy.isError && <p role="alert" className="text-sm text-destructive">{copy.error.message}</p>}
            <button type="button" disabled={copy.isPending}
              onClick={() => copy.mutate(open.id, { onSuccess: (p) => navigate(`/programs/${p.id}`) })}
              className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50">
              {copy.isPending ? 'Adding…' : 'Add program'}
            </button>
          </>
        )}
      </Sheet>
    </div>
  )
}
