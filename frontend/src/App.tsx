import { lazy, Suspense, useEffect } from 'react'
import { Route, Switch, useLocation } from 'wouter'
import { useQueryClient } from '@tanstack/react-query'
import { Loading } from '@/components/QueryStatus'
import TabBar from '@/components/TabBar'
import { useIsEditing } from '@/lib/editing'
import { useSignedIn } from '@/lib/auth'
import { flush, startOutbox } from '@/lib/store'
import SignIn from '@/screens/SignIn'
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
const Templates = lazy(() => import('@/screens/Templates'))
const WorkoutPlan = lazy(() => import('@/screens/WorkoutPlan'))
const Lift = lazy(() => import('@/screens/Lift'))
const SessionView = lazy(() => import('@/screens/SessionView'))
const LogFromNotes = lazy(() => import('@/screens/LogFromNotes'))
const Review = lazy(() => import('@/screens/review/Review'))
const Session = lazy(() => import('@/screens/session/Session'))
const Done = lazy(() => import('@/screens/session/Done'))

export default function App() {
  const [location] = useLocation()
  const editing = useIsEditing()
  // Review, a session in progress and edit mode have their own bottom bars, so the tabs step aside.
  const showTabs = !location.startsWith('/review') && !location.startsWith('/session') && !editing

  // Finished sessions waiting on the phone are sent now and whenever the connection returns.
  useEffect(() => startOutbox(), [])

  useEffect(() => {
    const id = setTimeout(() => Object.values(tabs).forEach((load) => load()), 1500)
    return () => clearTimeout(id)
  }, [])

  // Signing in (again) reloads everything, and sends sessions that waited on the phone meanwhile.
  // Signing out, by the button or because the server refused the pass, forgets what was loaded, so
  // the next person to sign in never sees it.
  const email = useSignedIn()
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!email) {
      queryClient.clear()
      return
    }
    queryClient.invalidateQueries()
    flush()
  }, [email, queryClient])

  if (!email) {
    return (
      <div className="mx-auto min-h-dvh max-w-md px-4 pt-[env(safe-area-inset-top)]">
        <SignIn />
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <main className="flex-1 px-4 pt-[env(safe-area-inset-top)] pb-28">
        <Suspense fallback={<Loading />}>
          <Switch>
            <Route path="/programs" component={Programs} />
            <Route path="/programs/templates" component={Templates} />
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
