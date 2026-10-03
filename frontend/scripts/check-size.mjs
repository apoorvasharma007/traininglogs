// Fails the build when the JavaScript a phone downloads before the first screen shows grows past
// the budget. That is the entry script plus what index.html preloads; screens loaded on demand
// are listed but not counted. Sizes are gzipped, which is what crosses the network.
import { readFileSync, readdirSync } from 'node:fs'
import { gzipSync } from 'node:zlib'

const BUDGET_KB = 120
const dist = new URL('../dist/', import.meta.url)
const html = readFileSync(new URL('index.html', dist), 'utf8')
const initial = new Set([...html.matchAll(/(?:src|href)="\/app\/assets\/([^"]+\.js)"/g)].map((m) => m[1]))

let total = 0
for (const f of readdirSync(new URL('assets/', dist)).filter((f) => f.endsWith('.js')).sort()) {
  const kb = gzipSync(readFileSync(new URL(`assets/${f}`, dist))).length / 1024
  const first = initial.has(f)
  if (first) total += kb
  console.log(`${first ? 'first load' : 'on demand '}  ${f.padEnd(36)} ${kb.toFixed(1)} KB`)
}
console.log(`First-load JavaScript ${total.toFixed(1)} KB of ${BUDGET_KB} KB budget`)
if (total > BUDGET_KB) {
  console.error('Over budget. Find what grew: npx vite-bundle-visualizer')
  process.exit(1)
}
