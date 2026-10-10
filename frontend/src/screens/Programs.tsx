import { ChevronRight, LayoutTemplate, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useSearch } from 'wouter'
import NameSheet from '@/components/NameSheet'
import { MenuGroup, MenuItem } from '@/components/Menu'
import Sheet from '@/components/Sheet'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { useCreateProgram, usePrograms, workoutName } from '@/lib/programs'
import type { Program } from '@/lib/types'
import { errorText } from '@/lib/errors'
import { BTN, SHEET_TITLE } from '@/lib/ui'
import { cn } from '@/lib/utils'

function summary(p: Program): string {
  const count = `${p.workouts.length} ${p.workouts.length === 1 ? 'workout' : 'workouts'}`
  const next = p.workouts.find((w) => w.id === p.next_workout_id)
  return p.following && next ? `${count}, next: ${workoutName(next)}` : count
}

export default function Programs() {
  const programs = usePrograms()
  const create = useCreateProgram()
  const [, navigate] = useLocation()
  // Train's Create Your Own lands here with ?new: straight to naming it.
  const search = useSearch()
  const [creating, setCreating] = useState(() => new URLSearchParams(search).has('new'))
  const [choosing, setChoosing] = useState(false) // "Create Your Own" or "From a Template"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <PageTitle>Programs</PageTitle>
        <button type="button" onClick={() => setChoosing(true)}
          className={cn(BTN.smallSecondary, 'flex items-center gap-1.5')}>
          <Plus size={18} aria-hidden /> New
        </button>
      </div>

      {programs.isPending && <Loading />}
      {programs.isError && <LoadError error={programs.error} retry={() => programs.refetch()} />}
      {programs.data?.length === 0 && (
        <div className="flex flex-col items-start gap-3 rounded-2xl bg-muted p-5 text-[15px]">
          <p className="font-semibold">No Programs Yet</p>
          <button type="button" onClick={() => setChoosing(true)}
            className={`${BTN.smallPrimary} flex items-center gap-1.5`}>
            <Plus size={18} aria-hidden /> New Program
          </button>
        </div>
      )}
      {programs.data && programs.data.length > 0 && (
        <div className="flex flex-col gap-2.5">
          {programs.data.map((p) => (
            <Link key={p.id} href={`/programs/${p.id}`}
              className="flex min-h-16 items-center gap-2.5 rounded-2xl border border-border bg-card px-4 py-2 transition active:scale-[0.98]">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex items-center gap-2 text-[15px] font-semibold">
                  {p.name}
                  {p.following && (
                    <span className="rounded-full bg-highlight-soft px-2 py-0.5 text-[11px] font-semibold text-highlight">
                      Following
                    </span>
                  )}
                </span>
                <span className="text-[13px] text-muted-foreground">{summary(p)}</span>
              </span>
              <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
            </Link>
          ))}
        </div>
      )}

      <Sheet open={choosing} onClose={() => setChoosing(false)} label="New Program">
        <span className={SHEET_TITLE}>New Program</span>
        <MenuGroup>
          <MenuItem icon={Plus} label="Create Your Own" onClick={() => { setChoosing(false); setCreating(true) }} />
          <MenuItem icon={LayoutTemplate} label="From a Template" onClick={() => { setChoosing(false); navigate('/programs/templates') }} />
        </MenuGroup>
      </Sheet>

      <NameSheet
        open={creating}
        title="New Program"
        label="Name"
        placeholder="Strength, Hypertrophy…"
        saveLabel="Create"
        busy={create.isPending}
        error={create.error ? errorText(create.error) : undefined}
        onClose={() => setCreating(false)}
        onSave={(name) =>
          create.mutate(name, {
            onSuccess: (p) => {
              setCreating(false)
              navigate(`/programs/${p.id}`)
            },
          })
        }
      />
    </div>
  )
}
