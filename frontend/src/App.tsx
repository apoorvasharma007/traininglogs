import { lazy, Suspense, useEffect } from 'react'
import { Route, Switch, useLocation } from 'wouter'
import { Loading } from '@/components/QueryStatus'
import TabBar from '@/components/TabBar'
import { startOutbox } from '@/lib/store'
import Train from '@/screens/Train'

// Only Train, the screen the app opens on, is in the first download. Everything else loads when
// first opened; the other tabs are also fetched in the background once the first screen is up,
// so switching tabs doesn't wait.
const tabs = {
  programs: () => import('@/screens/Programs'),
  progress: () => import('@/screens/Progress'),
  history: () => import('@/screens/History'),
  settings: () => import('@/screens/Settings'),
}
const Programs = lazy(tabs.programs)
const Progress = lazy(tabs.progress)
const History = lazy(tabs.history)
const Settings = lazy(tabs.settings)
const Program = lazy(() => import('@/screens/Program'))
const WorkoutPlan = lazy(() => import('@/screens/WorkoutPlan'))
const Lift = lazy(() => import('@/screens/Lift'))
const SessionView = lazy(() => import('@/screens/SessionView'))
const LogFromNotes = lazy(() => import('@/screens/LogFromNotes'))
const Review = lazy(() => import('@/screens/review/Review'))
const Session = lazy(() => import('@/screens/session/Session'))
const Done = lazy(() => import('@/screens/session/Done'))

export default function App() {
  const [location] = useLocation()
  // Review and a session in progress have their own bottom bars, so the tabs step aside there.
  const showTabs = !location.startsWith('/review') && !location.startsWith('/session')

  // Finished sessions waiting on the phone are sent now and whenever the connection returns.
  useEffect(() => startOutbox(), [])

  useEffect(() => {
    const id = setTimeout(() => Object.values(tabs).forEach((load) => load()), 1500)
    return () => clearTimeout(id)
  }, [])

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <main className="flex-1 px-4 pt-[env(safe-area-inset-top)] pb-28">
        <Suspense fallback={<Loading />}>
          <Switch>
            <Route path="/programs" component={Programs} />
            <Route path="/programs/:id" component={Program} />
            <Route path="/programs/:id/workouts/:wid" component={WorkoutPlan} />
            <Route path="/progress" component={Progress} />
            <Route path="/progress/:name" component={Lift} />
            <Route path="/history" component={History} />
            <Route path="/history/:id" component={SessionView} />
            <Route path="/settings" component={Settings} />
            <Route path="/log" component={LogFromNotes} />
            <Route path="/review/:id" component={Review} />
            <Route path="/session" component={Session} />
            <Route path="/session/done" component={Done} />
            <Route component={Train} />
          </Switch>
        </Suspense>
      </main>
      {showTabs && <TabBar />}
    </div>
  )
}
