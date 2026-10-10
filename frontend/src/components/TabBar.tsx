import { ChartLine, Clock, Dumbbell, List, SlidersHorizontal, type LucideIcon } from 'lucide-react'
import { Link, useLocation } from 'wouter'

const TABS: { path: string; label: string; icon: LucideIcon }[] = [
  { path: '/', label: 'Train', icon: Dumbbell },
  { path: '/programs', label: 'Programs', icon: List },
  { path: '/progress', label: 'Progress', icon: ChartLine },
  { path: '/history', label: 'History', icon: Clock },
  { path: '/settings', label: 'Settings', icon: SlidersHorizontal },
]

export default function TabBar() {
  const [location] = useLocation()

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 border-t border-border bg-card/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl backdrop-saturate-150"
    >
      <div className="mx-auto grid max-w-md grid-cols-5">
        {TABS.map(({ path, label, icon: Icon }) => {
          // A tab stays lit on its sub-screens: /progress/Squat lights Progress.
          const active = path === '/' ? location === '/' || location === '/log' : location.startsWith(path)
          return (
            <Link
              key={path}
              href={path}
              aria-current={active ? 'page' : undefined}
              className={`flex h-16 flex-col items-center justify-center gap-1 text-[11px] ${
                active ? 'font-semibold text-highlight' : 'font-medium text-muted-foreground'
              }`}
            >
              <Icon size={22} strokeWidth={1.8} aria-hidden />
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
