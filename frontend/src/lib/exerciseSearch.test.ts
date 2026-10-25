import { describe, expect, it } from 'vitest'
import { exerciseSearch } from './exerciseSearch'

const lib = (id: string, name: string, other_names: string[] = []) => ({ id, name, other_names })
const search = exerciseSearch({
  library: [
    lib('1', 'Bench Press (Barbell)', ['bench press', 'bench']),
    lib('2', 'Chest Press (Machine)', ['machine bench press']),
    lib('3', 'Romanian Deadlift (Barbell)', ['romanian deadlift', 'rdl', 'barbell rdl']),
    lib('4', 'Bulgarian Split Squat (Dumbbell)', ['bulgarian split squat']),
    lib('5', 'Clean (Barbell)', ['clean']),
  ],
  mine: [
    { id: 'a', name: 'Barbell Clean', exercise_id: '5', primary_muscles: [] },
    { id: 'd', name: 'Olympic Pull', exercise_id: '5', primary_muscles: [] },
    { id: 'b', name: 'Zercher Squat', exercise_id: null, primary_muscles: ['Vastus Muscles'] },
    { id: 'c', name: 'Shoulder Press', exercise_id: null, primary_muscles: [] },
  ],
})
const names = (q: string) => search(q).results.map((r) => r.name)

describe('exerciseSearch', () => {
  it('finds names by the start of a word', () => {
    expect(names('bul')).toEqual(['Bulgarian Split Squat (Dumbbell)'])
  })

  it('allows typos', () => {
    expect(names('romainan')).toEqual(['Romanian Deadlift (Barbell)'])
  })

  it('allows a wider typo, such as swapped letters, only when nothing else matches', () => {
    expect(names('benhc')).toEqual(['Bench Press (Barbell)', 'Chest Press (Machine)'])
    expect(names('bench')).toEqual(['Bench Press (Barbell)', 'Chest Press (Machine)'])
  })

  it('ranks a name match above a search word match', () => {
    expect(names('bench')).toEqual(['Bench Press (Barbell)', 'Chest Press (Machine)'])
  })

  it('shows the search word that matched when the name did not', () => {
    expect(search('rdl').results).toEqual([{ name: 'Romanian Deadlift (Barbell)', kind: 'library', matched: 'rdl' }])
    expect(search('bench').results[0].matched).toBeNull()
  })

  it('finds a library exercise by your linked name, without a row of its own', () => {
    expect(search('olympic').results).toEqual([{ name: 'Clean (Barbell)', kind: 'library', matched: 'Olympic Pull' }])
    expect(search('barbell clean').results).toEqual([{ name: 'Clean (Barbell)', kind: 'library', matched: null }])
  })

  it('includes your custom exercises and unrecognized names', () => {
    expect(search('zercher').results).toEqual([{ name: 'Zercher Squat', kind: 'custom', matched: null }])
    expect(search('shoulder').results).toEqual([{ name: 'Shoulder Press', kind: 'unrecognized', matched: null }])
  })

  it('offers Add only when nothing has exactly the typed name', () => {
    expect(search('  bench   PRESS (barbell) ').canAdd).toBe(false)
    expect(search('barbell clean').canAdd).toBe(false)
    expect(search('bench').canAdd).toBe(true)
    expect(search(' ').canAdd).toBe(false)
  })
})
