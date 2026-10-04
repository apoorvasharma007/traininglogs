import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { Router } from 'wouter'
import { memoryLocation } from 'wouter/memory-location'
import App from './App'

/** Renders the whole app at `path`, with a fresh data cache and an in-memory address bar. */
export function renderApp(path: string) {
  const location = memoryLocation({ path, record: true })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Router hook={location.hook}>
        <App />
      </Router>
    </QueryClientProvider>,
  )
  return location
}

type Handler = (body: unknown) => unknown

/** Replaces fetch with canned replies keyed by "METHOD /path"; records every call. */
export function fakeApi(routes: Record<string, unknown | Handler>) {
  const calls: { key: string; body: unknown }[] = []
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${url}`
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ key, body })
    if (!(key in routes)) return new Response(JSON.stringify({ detail: `no fake for ${key}` }), { status: 404 })
    const route = routes[key]
    const reply = typeof route === 'function' ? (route as Handler)(body) : route
    return new Response(JSON.stringify(reply), { status: 200 })
  }) as typeof fetch
  return calls
}
