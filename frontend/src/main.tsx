import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Router } from 'wouter'
import { useHashLocation } from 'wouter/use-hash-location'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

// Screens live after the # (/app/#/history), so reloading a screen never reaches an API route
// with the same name, and the server needs no fallback rules.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router hook={useHashLocation}>
        <App />
      </Router>
    </QueryClientProvider>
  </StrictMode>,
)
