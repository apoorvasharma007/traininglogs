// Fails the build when the JavaScript a phone downloads on first load grows past the budget.
// Sizes are gzipped, which is what actually crosses the network.
import { readdirSync, readFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'

const BUDGET_KB = 120
const dir = new URL('../dist/assets/', import.meta.url)
const files = readdirSync(dir).filter((f) => f.endsWith('.js') || f.endsWith('.css'))
let total = 0
for (const f of files) {
  const kb = gzipSync(readFileSync(new URL(f, dir))).length / 1024
  total += f.endsWith('.js') ? kb : 0
  console.log(`${f.padEnd(40)} ${kb.toFixed(1)} KB`)
}
console.log(`JavaScript total ${total.toFixed(1)} KB of ${BUDGET_KB} KB budget`)
if (total > BUDGET_KB) {
  console.error('Over budget. Find what grew: npx vite-bundle-visualizer')
  process.exit(1)
}
