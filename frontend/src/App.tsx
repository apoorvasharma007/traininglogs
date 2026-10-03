import { Route, Switch } from 'wouter'
import TabBar from '@/components/TabBar'
import History from '@/screens/History'
import Programs from '@/screens/Programs'
import Progress from '@/screens/Progress'
import Settings from '@/screens/Settings'
import Train from '@/screens/Train'

export default function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <main className="flex-1 px-4 pt-[calc(env(safe-area-inset-top)+3.5rem)] pb-28">
        <Switch>
          <Route path="/programs" component={Programs} />
          <Route path="/progress" component={Progress} />
          <Route path="/history" component={History} />
          <Route path="/settings" component={Settings} />
          <Route component={Train} />
        </Switch>
      </main>
      <TabBar />
    </div>
  )
}
