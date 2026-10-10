import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { useCopyTemplate, useTemplates } from '@/lib/programs'
import PlanSets from '@/components/PlanSets'
import type { ProgramTemplate } from '@/lib/types'
import { errorText } from '@/lib/errors'
import { BTN, SHEET_TITLE } from '@/lib/ui'

/** Ready-made programs. Tapping one shows its workouts; "Add Program" copies it into yours. */
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
        <div className="flex flex-col gap-2.5">
          {templates.data.map((t) => (
            <button key={t.id} type="button" onClick={() => { copy.reset(); setOpen(t) }}
              className="flex min-h-16 w-full items-center gap-2.5 rounded-2xl border border-border bg-card px-4 py-2 text-left transition active:scale-[0.98]">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-[15px] font-semibold">{t.name}</span>
                <span className="text-[13px] text-muted-foreground">{t.days}</span>
              </span>
              <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
            </button>
          ))}
        </div>
      )}

      <Sheet open={open != null} onClose={() => setOpen(null)} label={open?.name ?? 'Template'}>
        {open && (
          <>
            <span className={SHEET_TITLE}>{open.name}</span>
            <div className="flex max-h-[55dvh] flex-col gap-3 overflow-y-auto">
              {open.workouts.map((w) => (
                <section key={w.name}>
                  <h2 className="mb-1 text-[13px] font-semibold text-muted-foreground">{w.name}</h2>
                  <ul>
                    {w.exercises.map((e) => (
                      <li key={e.name} className="flex min-h-8 items-center justify-between gap-3 text-[15px]">
                        <span className="truncate">{e.name}</span>
                        <PlanSets exercise={e} />
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
            {copy.isError && <p role="alert" className="text-[15px] text-destructive">{errorText(copy.error)}</p>}
            <button type="button" disabled={copy.isPending}
              onClick={() => copy.mutate(open.id, { onSuccess: (p) => navigate(`/programs/${p.id}`) })}
              className={BTN.primary}>
              {copy.isPending ? 'Adding…' : 'Add Program'}
            </button>
          </>
        )}
      </Sheet>
    </div>
  )
}
