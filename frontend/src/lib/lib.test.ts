import { describe, expect, it } from 'vitest'
import { niceScale } from './chart'
import { dayLabel, groupByWeek, kg, repsText } from './format'
import { inRange, liftValue, setText } from './lifts'
import { editsFor, exercisePathOf, stepReps, stepWeight, type SetDraft } from './review'

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

  it('steps weight and plain reps', () => {
    expect(stepWeight('120', 2.5)).toBe('122.5')
    expect(stepWeight('1', -2.5)).toBe('0')
    expect(stepReps('2', 1)).toBe('3')
    expect(stepReps('8+1', 1)).toBeNull()
    expect(stepReps('', 1)).toBe('1')
  })

  it('finds the exercise of a set', () => {
    expect(exercisePathOf('exercises.2.warmup_sets.0')).toBe('exercises.2')
  })
})
