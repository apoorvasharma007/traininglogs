import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import PageTitle from '@/components/PageTitle'
import { loadSession } from '@/lib/store'
import { startSession } from '@/lib/startSession'
import type { LiveSession } from '@/lib/session'

// The full home screen (next workout, deload reminder) comes in step 6.
export default function Train() {
  const [, navigate] = useLocation()
  const [current, setCurrent] = useState<LiveSession | null>(null)
  useEffect(() => {
    loadSession().then(setCurrent)
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>Train</PageTitle>
      {current && (
        <Link href="/session" className="flex flex-col gap-1 rounded-2xl border border-border bg-card p-4">
          <span className="text-xs font-semibold text-highlight">Session in progress</span>
          <span className="text-lg font-bold">{current.title}</span>
          <span className="text-sm text-muted-foreground">Tap to resume</span>
        </Link>
      )}
      <div className="grid grid-cols-2 gap-2.5">
        <button type="button" onClick={() => startSession('blank').then(() => navigate('/session'))}
          className="flex h-12 items-center justify-center rounded-2xl border border-border bg-card text-sm font-semibold">
          Blank workout
        </button>
        <Link href="/log" className="flex h-12 items-center justify-center rounded-2xl border border-border bg-card text-sm font-semibold">
          Log from notes
        </Link>
      </div>
    </div>
  )
}
