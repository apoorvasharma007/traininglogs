import { ChevronRight, Repeat } from 'lucide-react'
import Parts from '@/components/Parts'
import { useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import DragList from '@/components/DragList'
import DraftBar from '@/components/DraftBar'
import BottomBar from '@/components/BottomBar'
import HeaderName, { EditButton } from '@/components/HeaderName'
import NameSheet from '@/components/NameSheet'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { useEditingFlag } from '@/lib/editing'
import { dayLabel } from '@/lib/format'
import { usePrograms, useProgram, useProgramChange, workoutName } from '@/lib/programs'
import type { Program as ProgramT, Workout } from '@/lib/types'

/** A program's workouts. Opens for looking; Edit shows renaming, reordering and settings. */
export default function Program({ params }: { params: { id: string } }) {
  const program = useProgram(params.id)
  const change = useProgramChange(params.id)
  const [, navigate] = useLocation()
  // While editing, renaming and reordering change only this draft; Save writes it.
  const [draft, setDraft] = useState<{ name: string; order: string[] } | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const editing = draft != null
  useEditingFlag(editing)
  const [archiving, setArchiving] = useState(false)
  const [adding, setAdding] = useState(false)
  const [pickingWeeks, setPickingWeeks] = useState(false)
  const [weeksChoice, setWeeksChoice] = useState(4)
  const [confirm, setConfirm] = useState<'follow' | 'unfollow' | null>(null)
  const programs = usePrograms()
  const otherFollowed = programs.data?.find((x) => x.following && x.id !== params.id)
  const p = program.data
  const base = `/programs/${params.id}`
  const savedOrder = p?.workouts.map((w) => w.id) ?? []
  const savedWeeks = Math.round((p?.deload_after_days ?? 28) / 7)
  const nameChanged = !!p && !!draft && draft.name.trim() !== '' && draft.name.trim() !== p.name
  const orderChanged = !!draft && draft.order.join() !== savedOrder.join()
  const dirty = nameChanged || orderChanged

  async function save(): Promise<boolean> {
    if (!draft) return true
    setSaving(true)
    setSaveError(null)
    try {
      if (nameChanged) await change.mutateAsync({ path: base, method: 'PATCH', body: { name: draft.name.trim() } })
      if (orderChanged) await change.mutateAsync({ path: `${base}/workout-order`, method: 'PUT', body: { workout_ids: draft.order } })
      setDraft(null)
      return true
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e))
      return false
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={editing ? 'pb-32' : 'pb-6'}>
      <ScreenHeader
        back={editing ? undefined : '/programs'}
        backLabel="Back to Programs"
        title={p?.name ?? 'Program'}
        titleSlot={
          draft ? (
            <HeaderName label="Program name" value={draft.name} placeholder="Program name"
              onChange={(name) => setDraft({ ...draft, name })} />
          ) : undefined
        }
        action={p && !editing && <EditButton onClick={() => setDraft({ name: p.name, order: savedOrder })} />}
      />
      {program.isPending && <Loading />}
      {program.isError && <LoadError error={program.error} retry={() => program.refetch()} />}
      {p && (
        <div className="flex flex-col gap-4">
          <p className="-mt-2 flex items-center gap-1.5 px-1 text-[13px] text-muted-foreground">
            {p.following && <span className="mr-1.5 font-semibold text-highlight">Following</span>}
            <Repeat size={13} aria-label="on repeat" />
            {p.workouts.length} {p.workouts.length === 1 ? 'workout' : 'workouts'}
          </p>

          {p.workouts.length === 0 && (
            <p className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
              No workouts yet. {editing ? 'Add the first one.' : 'Tap Edit to add the first one.'}
            </p>
          )}

          {p.workouts.length > 0 &&
            (draft ? (
              <DragList
                items={draft.order.flatMap((id) => p.workouts.filter((w) => w.id === id))}
                keyOf={(w) => w.id}
                label={workoutName}
                onReorder={(ids) => setDraft({ ...draft, order: ids })}
              >
                {(w) => <WorkoutRow program={p} workout={w} />}
              </DragList>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-border bg-card">
                {p.workouts.map((w) => (
                  <div key={w.id} className="flex items-center border-t border-border pr-3 first:border-t-0">
                    <WorkoutRow program={p} workout={w} href={`${base}/workouts/${w.id}`} />
                    <ChevronRight size={18} aria-hidden className="shrink-0 text-faint-foreground" />
                  </div>
                ))}
              </div>
            ))}

          {change.isError && <p role="alert" className="px-1 text-sm text-destructive">{change.error.message}</p>}

          {editing && (
            <button type="button" disabled={change.isPending || saving}
              // Adding opens the new workout, so unsaved changes here are saved first.
              onClick={async () => { if (!dirty || (await save())) setAdding(true) }}
              className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
              + Add workout
            </button>
          )}

          {!p.following && !editing && (
            <BottomBar aboveTabs>
              <button type="button" disabled={change.isPending}
                onClick={() => (otherFollowed ? setConfirm('follow') : change.mutate({ path: `${base}/follow`, method: 'POST' }))}
                className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
                Follow This Program
              </button>
            </BottomBar>
          )}

          <div className="mt-6 flex flex-col items-center gap-1">
            <button type="button" onClick={() => { setWeeksChoice(savedWeeks); setPickingWeeks(true) }} className="h-10 px-2 text-[13px] text-muted-foreground">
              Deload reminder every <span className="font-semibold text-foreground">{Math.round(p.deload_after_days / 7)} weeks</span>
            </button>
            {p.following && (
              <button type="button" disabled={change.isPending} onClick={() => setConfirm('unfollow')}
                className="h-10 px-2 text-[13px] font-semibold text-muted-foreground">
                Stop Following
              </button>
            )}
          </div>

          {editing && (
            <button type="button" onClick={() => setArchiving(true)} className="h-11 text-sm font-semibold text-destructive">
              Delete Program
            </button>
          )}
        </div>
      )}

      {editing && (
        <DraftBar dirty={dirty} busy={saving} error={saveError} onSave={save}
          onCancel={() => { setDraft(null); setSaveError(null) }} />
      )}

      <NameSheet open={adding} title="New workout" label="Name" initial={`Workout ${(p?.workouts.length ?? 0) + 1}`}
        saveLabel="Add workout" allowBlank busy={change.isPending} error={change.error?.message}
        onClose={() => setAdding(false)}
        onSave={(name) => {
          const n = (p?.workouts.length ?? 0) + 1
          change.mutate(
            { path: `${base}/workouts`, method: 'POST', body: { name: name.toLowerCase() === `workout ${n}` ? null : name } },
            { onSuccess: (next) => { setAdding(false); navigate(`${base}/workouts/${next.workouts[next.workouts.length - 1].id}`) } },
          )
        }} />

      <Sheet open={pickingWeeks} onClose={() => setPickingWeeks(false)} label="Deload reminder">
        <div className="flex flex-col gap-1">
          <span className="text-[17px] font-semibold">Deload reminder</span>
          <span className="text-sm text-muted-foreground">Remind me to take a lighter week after this many weeks of training.</span>
        </div>
        <div role="group" aria-label="Weeks" className="grid grid-cols-5 gap-1.5">
          {[3, 4, 5, 6, 8].map((weeks) => {
            const on = weeksChoice === weeks
            return (
              <button key={weeks} type="button" aria-pressed={on} onClick={() => setWeeksChoice(weeks)}
                className={`h-12 rounded-xl text-[15px] font-semibold ${on ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                {weeks}
              </button>
            )
          })}
        </div>
        <span className="-mt-2 text-center text-xs text-muted-foreground">weeks</span>
        <button type="button" disabled={change.isPending || weeksChoice === savedWeeks}
          onClick={() => change.mutate({ path: base, method: 'PATCH', body: { deload_after_days: weeksChoice * 7 } }, { onSuccess: () => setPickingWeeks(false) })}
          className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-40">
          Save
        </button>
      </Sheet>

      <ConfirmSheet open={confirm === 'unfollow'} title={`Stop following ${p?.name ?? 'this program'}?`}
        body="Train won't show its next workout any more. The program and its history stay; you can follow it again any time."
        confirmLabel="Stop Following" busy={change.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={() => change.mutate({ path: `${base}/unfollow`, method: 'POST' }, { onSuccess: () => setConfirm(null) })} />

      <ConfirmSheet open={confirm === 'follow'} tone="primary" title={`Follow ${p?.name ?? 'this program'}?`}
        body={`You'll stop following ${otherFollowed?.name ?? 'your current program'}. Its history stays, and you can switch back any time.`}
        confirmLabel="Follow This Program" busy={change.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={() => change.mutate({ path: `${base}/follow`, method: 'POST' }, { onSuccess: () => setConfirm(null) })} />

      <ConfirmSheet open={archiving} title={`Delete ${p?.name ?? 'program'}?`}
        body="It disappears from the app. Sessions you logged from it stay in History."
        confirmLabel="Delete Program" busy={change.isPending}
        onClose={() => setArchiving(false)}
        onConfirm={() => change.mutate({ path: base, method: 'DELETE' }, { onSuccess: () => navigate('/programs') })} />
    </div>
  )
}

/** A workout in the list: a link while viewing; while editing, only something to drag. */
function WorkoutRow({ program, workout: w, href }: { program: ProgramT; workout: Workout; href?: string }) {
  const body = (
    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
      <span className="flex items-center gap-2 text-[15px] font-semibold">
        {workoutName(w)}
        {program.following && w.id === program.next_workout_id && (
          <span className="rounded-full bg-highlight-soft px-2 py-0.5 text-[11px] font-semibold text-highlight">Next</span>
        )}
      </span>
      {w.exercises.length
        ? <Parts className="text-xs text-muted-foreground" items={w.exercises.map((e) => e.name)} />
        : <span className="text-xs text-muted-foreground">No exercises yet</span>}
      {w.last_done && <span className="text-xs text-faint-foreground">Last done {dayLabel(w.last_done)}</span>}
    </span>
  )
  return href ? (
    <Link href={href} className="flex min-h-16 min-w-0 flex-1 items-center gap-3 py-2 pl-4 active:bg-muted">{body}</Link>
  ) : (
    <div className="flex min-h-16 min-w-0 flex-1 items-center gap-3 py-2 pl-4">{body}</div>
  )
}
