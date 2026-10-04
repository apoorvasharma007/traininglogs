import { ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'wouter'
import NameSheet from '@/components/NameSheet'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { useCreateProgram, usePrograms, workoutTitle } from '@/lib/programs'
import type { Program } from '@/lib/types'

function summary(p: Program): string {
  const count = `${p.workouts.length} ${p.workouts.length === 1 ? 'workout' : 'workouts'}`
  const next = p.workouts.find((w) => w.id === p.next_workout_id)
  return p.following && next ? `${count} · next: ${workoutTitle(next)}` : count
}

export default function Programs() {
  const programs = usePrograms()
  const create = useCreateProgram()
  const [, navigate] = useLocation()
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <PageTitle>Programs</PageTitle>
        <button type="button" onClick={() => setCreating(true)}
          className="flex h-10 items-center gap-1.5 rounded-xl border border-border bg-card px-3.5 text-sm font-semibold transition active:scale-95">
          <Plus size={16} aria-hidden /> New
        </button>
      </div>

      {programs.isPending && <Loading />}
      {programs.isError && <LoadError error={programs.error} retry={() => programs.refetch()} />}
      {programs.data?.length === 0 && (
        <div className="flex flex-col gap-2 rounded-2xl border border-dashed border-border p-5 text-sm">
          <p className="font-semibold">No programs yet</p>
          <p className="text-muted-foreground">
            A program is workouts in order. After the last one it starts again at 1, until you reach your goal.
          </p>
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

      <NameSheet
        open={creating}
        title="New program"
        label="Name"
        placeholder="Strength, Hypertrophy…"
        saveLabel="Create"
        busy={create.isPending}
        error={create.error?.message}
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
