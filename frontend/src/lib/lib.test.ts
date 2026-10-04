import { describe, expect, it } from 'vitest'
import { niceScale } from './chart'
import { dayLabel, groupByWeek, kg, repsText } from './format'
import { inRange, liftValue, setText } from './lifts'
import { editsFor, exercisePathOf, type SetDraft } from './review'

const ws = { number: 1, weight_kg: 100, reps_full: null, reps_partial: null, left_reps_full: null, right_reps_full: null, rpe: null, notes: null }

describe('format', () => {
  it('labels dates without shifting the day', () => {
    expect(dayLabel('2026-10-02')).toBe('Fri 2 Oct')
  })

  it('rounds weights to one decimal', () => {
    expect(kg(133.333)).toBe('133.3')
    expect(kg(125)).toBe('125')
  })

  it('writes reps as plain, partial or per side', () => {
    expect(repsText({ ...ws, reps_full: 8 })).toBe('8')
    expect(repsText({ ...ws, reps_full: 8, reps_partial: 1 })).toBe('8+1')
    expect(repsText({ ...ws, left_reps_full: 8, right_reps_full: 7 })).toBe('8L / 7R')
    expect(repsText(ws)).toBe('–')
  })

  it('groups by calendar week starting Monday, newest first', () => {
    const days = ['2026-10-04', '2026-09-28', '2026-09-27', '2026-09-21']
    const groups = groupByWeek(days, (d) => d, new Date(2026, 9, 4))
    expect(groups.map((g) => [g.title, g.items])).toEqual([
      ['This week', ['2026-10-04', '2026-09-28']],
      ['21 Sept to 27 Sept', ['2026-09-27', '2026-09-21']],
    ])
  })
})

describe('lifts', () => {
  it('shows kg or reps by measure', () => {
    expect(liftValue({ measure: 'estimated_max' }, 133.33)).toBe('133.3 kg')
    expect(liftValue({ measure: 'bodyweight_reps' }, 19)).toBe('19 reps')
  })

  it('writes the set behind a value', () => {
    expect(setText({ number: 1, weight_kg: 125, reps: 2, rpe: 9 })).toBe('125 kg × 2 @ 9')
    expect(setText({ number: 1, weight_kg: 0, reps: 19, rpe: null })).toBe('BW × 19')
  })

  it('keeps points within a range of the newest one', () => {
    const pts = [{ date: '2026-07-01' }, { date: '2026-09-10' }, { date: '2026-10-02' }]
    expect(inRange(pts, 28).map((p) => p.date)).toEqual(['2026-09-10', '2026-10-02'])
    expect(inRange(pts, null)).toHaveLength(3)
  })
})

describe('chart scale', () => {
  it('rounds bounds outward to a step', () => {
    expect(niceScale(106.7, 133.3)).toEqual({ lo: 100, hi: 140, step: 10 })
  })

  it('handles a single value', () => {
    const { lo, hi } = niceScale(19, 19)
    expect(lo).toBeLessThanOrEqual(19)
    expect(hi).toBeGreaterThanOrEqual(19)
  })
})

describe('review edits', () => {
  const before: SetDraft = { kind: 'working', weight: '120', reps: '2', rpe: null, note: '' }

  it('sends only what changed', () => {
    expect(editsFor('exercises.0.sets.0', before, { ...before, weight: '122.5', rpe: 8 })).toEqual([
      { path: 'exercises.0.sets.0', field: 'weight_kg', value: 122.5 },
      { path: 'exercises.0.sets.0', field: 'rpe', value: 8 },
    ])
    expect(editsFor('p', before, { ...before })).toEqual([])
  })

  it('clears with an empty string', () => {
    expect(editsFor('p', { ...before, rpe: 8, note: 'x' }, { ...before, rpe: null, note: '' })).toEqual([
      { path: 'p', field: 'rpe', value: '' },
      { path: 'p', field: 'notes', value: '' },
    ])
  })

  it('writes warmup reps as a number', () => {
    const w: SetDraft = { kind: 'warmup', weight: '80', reps: '', rpe: null, note: '' }
    expect(editsFor('p', w, { ...w, reps: '5' })).toEqual([{ path: 'p', field: 'rep_count', value: 5 }])
  })

  it('finds the exercise of a set', () => {
    expect(exercisePathOf('exercises.2.warmup_sets.0')).toBe('exercises.2')
  })
})

import { effortLevel } from './effort'
import { warmupSets } from './warmup'

describe('warmup ramps', () => {
  it('builds each ramp from the first working weight, rounded to 2.5 kg', () => {
    expect(warmupSets('full', 125)).toEqual([
      { kg: 20, reps: 10 }, { kg: 57.5, reps: 8 }, { kg: 82.5, reps: 5 }, { kg: 100, reps: 3 }, { kg: 112.5, reps: 1 },
    ])
    expect(warmupSets('short', 125)).toEqual([{ kg: 62.5, reps: 5 }, { kg: 87.5, reps: 4 }, { kg: 112.5, reps: 2 }])
    expect(warmupSets('531', 125)).toEqual([{ kg: 50, reps: 5 }, { kg: 62.5, reps: 5 }, { kg: 75, reps: 3 }])
  })

  it('never goes below the empty bar', () => {
    expect(warmupSets('short', 30).map((s) => s.kg)).toEqual([20, 20, 27.5])
  })
})

describe('effort', () => {
  it('maps RPE to Moderate, Hard and All out', () => {
    expect([null, 6, 7, 7.5, 8, 8.5, 9, 9.5, 10].map(effortLevel)).toEqual([0, 1, 1, 1, 2, 2, 2, 3, 3])
  })
})

import { amountText, parseAmount } from './movements'

describe('movement amounts', () => {
  it('reads reps or a time', () => {
    expect(parseAmount('10')).toEqual({ reps: 10, duration_seconds: null })
    expect(parseAmount('3 min')).toEqual({ reps: null, duration_seconds: 180 })
    expect(parseAmount('45s')).toEqual({ reps: null, duration_seconds: 45 })
    expect(parseAmount('')).toEqual({ reps: null, duration_seconds: null })
  })

  it('writes them back the same way', () => {
    expect(['10', '3 min', '45 s', ''].map((t) => amountText(parseAmount(t)))).toEqual(['10', '3 min', '45 s', ''])
  })
})

import { sessionName } from './format'

describe('session names', () => {
  it('uses the given name, else the first exercises', () => {
    expect(sessionName({ focus: 'Workout 3', exercises: ['Squat'] })).toBe('Workout 3')
    expect(sessionName({ focus: null, exercises: ['Squat', 'Bench press', 'Pull ups', 'Calf raise'] })).toBe('Squat · Bench press · Pull ups …')
    expect(sessionName({ focus: '', exercises: [] })).toBe('Session')
  })
})
