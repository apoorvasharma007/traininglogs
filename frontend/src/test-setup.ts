import '@testing-library/jest-dom/vitest'
import 'fake-indexeddb/auto'
import { afterEach, beforeEach } from 'vitest'
import { resetOutboxForTests } from '@/lib/store'

// jsdom lacks matchMedia, which the drawer (vaul) reads.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

// jsdom lacks pointer capture, which the drawer uses for dragging.
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
  Element.prototype.hasPointerCapture = () => false
}

// The send queue keeps its state in memory; a send left running by one test must not leak into the next.
afterEach(() => resetOutboxForTests())

// Every test starts signed in, with a pass that won't need renewing; sign-in tests sign out first.
beforeEach(() => {
  localStorage.setItem(
    'tl_session',
    JSON.stringify({ access_token: 'test-pass', refresh_token: 'r', expires_at: Date.now() + 3_600_000, email: 'a@example.com' }),
  )
})

// jsdom has no layout, so no scrolling.
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
