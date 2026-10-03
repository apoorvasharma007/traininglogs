import { Route, Switch, useLocation } from 'wouter'
import TabBar from '@/components/TabBar'
import History from '@/screens/History'
import Lift from '@/screens/Lift'
import LogFromNotes from '@/screens/LogFromNotes'
import Programs from '@/screens/Programs'
import Progress from '@/screens/Progress'
import Review from '@/screens/review/Review'
import SessionView from '@/screens/SessionView'
import Settings from '@/screens/Settings'
import Train from '@/screens/Train'

export default function App() {
  const [location] = useLocation()
  // Review has its own bottom bar (Confirm), so the tabs step aside there.
  const showTabs = !location.startsWith('/review')

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <main className="flex-1 px-4 pt-[env(safe-area-inset-top)] pb-28">
        <Switch>
          <Route path="/programs" component={Programs} />
          <Route path="/progress" component={Progress} />
          <Route path="/progress/:name" component={Lift} />
          <Route path="/history" component={History} />
          <Route path="/history/:id" component={SessionView} />
          <Route path="/settings" component={Settings} />
          <Route path="/log" component={LogFromNotes} />
          <Route path="/review/:id" component={Review} />
          <Route component={Train} />
        </Switch>
      </main>
      {showTabs && <TabBar />}
    </div>
  )
}
