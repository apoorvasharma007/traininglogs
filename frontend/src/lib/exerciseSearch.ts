// The exercise name box's search (exercise-library-plan.md, section 9): library exercises, your
// custom exercises and your unrecognized names, closest match first, typos allowed. A name of
// yours linked to a library exercise is a search word for that exercise, like its other names.
import MiniSearch from 'minisearch'
import type { ExercisesOut } from '@/lib/types'

export type ExerciseResult = {
  name: string
  kind: 'library' | 'custom' | 'unrecognized'
  matched: string | null // the search word that matched when the name didn't: `Matches "rdl"`
}

type Doc = ExerciseResult & { id: string; words: string[] }

const tokenize: (text: string) => string[] = MiniSearch.getDefault('tokenize')
const nameKey = (name: string) => name.split(/\s+/).filter(Boolean).join(' ').toLowerCase()

/** Builds the index once; the returned function searches it on each keystroke. `canAdd` is true
 *  when no exercise has exactly the typed name, so "Add '…' as your own" can show. */
export function exerciseSearch({ library, mine }: ExercisesOut) {
  const aliases = new Map<string, string[]>()
  for (const m of mine) if (m.exercise_id) aliases.set(m.exercise_id, [...(aliases.get(m.exercise_id) ?? []), m.name])
  const docs: Doc[] = [
    ...library.map((e) => ({ id: `library-${e.id}`, name: e.name, kind: 'library' as const, matched: null, words: [...e.other_names, ...(aliases.get(e.id) ?? [])] })),
    ...mine.filter((m) => !m.exercise_id).map((m) => ({
      id: `mine-${m.id}`, name: m.name, kind: m.primary_muscles.length ? 'custom' as const : 'unrecognized' as const, matched: null, words: [],
    })),
  ]
  const byId = new Map(docs.map((d) => [d.id, d]))
  const names = new Set([...library, ...mine].map((e) => nameKey(e.name)))
  const index = new MiniSearch<Doc>({
    fields: ['name', 'words'],
    stringifyField: (value) => (Array.isArray(value) ? value.join(' ') : value),
    searchOptions: { boost: { name: 2 }, prefix: true, fuzzy: 0.2, combineWith: 'AND' },
  })
  index.addAll(docs)

  return (query: string): { results: ExerciseResult[]; canAdd: boolean } => {
    const key = nameKey(query)
    // A wider typo allowance only when the strict one finds nothing: "benhc" finds Bench Press,
    // but "bench" doesn't also find Serratus Punch.
    const fuzzy = index.search(query).length ? 0.2 : (t: string) => (t.length >= 5 ? 2 : t.length >= 4 ? 1 : 0)
    const byName = new Set(index.search(query, { fields: ['name'], fuzzy }).map((hit) => hit.id))
    // Exactly the typed name or search word first, then the closest match, then A to Z.
    const exact = (id: string) => [byId.get(id)!.name, ...byId.get(id)!.words].some((w) => nameKey(w) === key)
    const hits = index.search(query, { fuzzy }).sort((a, b) =>
      Number(exact(b.id)) - Number(exact(a.id)) || b.score - a.score || byId.get(a.id)!.name.localeCompare(byId.get(b.id)!.name))
    const results = hits.slice(0, 6).map((hit) => {
      const { name, kind, words } = byId.get(hit.id)!
      if (byName.has(hit.id)) return { name, kind, matched: null }
      // The search word typed exactly, else the one holding the most matched terms, the shortest on a tie.
      const covers = (w: string) => (nameKey(w) === key ? Infinity : tokenize(w.toLowerCase()).filter((t) => hit.terms.includes(t)).length)
      const best = words.reduce((a, b) => (covers(b) > covers(a) || (covers(b) === covers(a) && b.length < a.length) ? b : a))
      return { name, kind, matched: best }
    })
    return { results, canAdd: key !== '' && !names.has(key) }
  }
}
