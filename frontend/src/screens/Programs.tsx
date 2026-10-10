import { ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'wouter'
import NameSheet from '@/components/NameSheet'
import Sheet from '@/components/Sheet'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { useCreateProgram, usePrograms, workoutName } from '@/lib/programs'
import type { Program } from '@/lib/types'
import { errorText } from '@/lib/errors'

function summary(p: Program): string {
  const count = `${p.workouts.length} ${p.workouts.length === 1 ? 'workout' : 'workouts'}`
  const next = p.workouts.find((w) => w.id === p.next_workout_id)
  return p.following && next ? `${count}, next: ${workoutName(next)}` : count
}

export default function Programs() {
  const programs = usePrograms()
  const create = useCreateProgram()
  const [, navigate] = useLocation()
  const [creating, setCreating] = useState(false)
  const [choosing, setChoosing] = useState(false) // "Create Your Own" or "From a Template"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <PageTitle>Programs</PageTitle>
        <button type="button" onClick={() => setChoosing(true)}
          className="flex h-10 items-center gap-1.5 rounded-xl border border-border bg-card px-3.5 text-sm font-semibold transition active:scale-95">
          <Plus size={16} aria-hidden /> New
        </button>
      </div>

      {programs.isPending && <Loading />}
      {programs.isError && <LoadError error={programs.error} retry={() => programs.refetch()} />}
      {programs.data?.length === 0 && (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-dashed border-border p-5 text-sm">
          <p className="font-semibold">No programs yet</p>
          <button type="button" onClick={() => setChoosing(true)}
            className="flex h-10 items-center gap-1.5 rounded-xl bg-primary px-3.5 font-semibold text-primary-foreground transition active:scale-95">
            <Plus size={16} aria-hidden /> New Program
          </button>
        </div>
      )}
      {programs.data && programs.data.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          {programs.data.map((p) => (
            <Link key={p.id} href={`/programs/${p.id}`}
              className="flex min-h-16 items-center gap-2.5 border-t border-border px-4 py-2 first:border-t-0 active:bg-muted">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex items-center gap-2 text-[15px] font-semibold">
                  {p.name}
                  {p.following && (
                    <span className="rounded-full bg-highlight-soft px-2 py-0.5 text-[11px] font-semibold text-highlight">
                      Following
                    </span>
                  )}
                </span>
                <span className="text-xs text-muted-foreground">{summary(p)}</span>
              </span>
              <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
            </Link>
          ))}
        </div>
      )}

      <Sheet open={choosing} onClose={() => setChoosing(false)} label="New Program">
        <span className="text-[17px] font-semibold">New Program</span>
        <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
          <button type="button" onClick={() => { setChoosing(false); setCreating(true) }}
            className="flex h-13 items-center px-4 text-left text-[15px] font-semibold active:bg-muted">
            Create Your Own
          </button>
          <Link href="/programs/templates" onClick={() => setChoosing(false)}
            className="flex h-13 items-center justify-between border-t border-border px-4 text-[15px] font-semibold active:bg-muted">
            From a Template
            <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
          </Link>
        </div>
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
