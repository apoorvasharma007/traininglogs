import { Link } from 'wouter'
import PageTitle from '@/components/PageTitle'

// The full home screen (next workout, deload reminder, blank workout) comes in step 6.
export default function Train() {
  return (
    <div className="flex flex-col gap-4">
      <PageTitle>Train</PageTitle>
      <Link
        href="/log"
        className="flex h-12 items-center justify-center rounded-2xl border border-border bg-card font-semibold"
      >
        Log from notes
      </Link>
    </div>
  )
}
