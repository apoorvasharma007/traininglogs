import { describe, expect, it } from 'vitest'
import { mark, markOf, musclesOf, tapGroup } from './muscleMarks'

describe('mark', () => {
  it('marks a muscle primary', () => {
    expect(mark(['Abs'], [], 'Obliques', 'primary')).toEqual([['Abs', 'Obliques'], []])
  })

  it('moves a primary muscle to secondary', () => {
    expect(mark(['Abs', 'Obliques'], ['Lats'], 'Abs', 'secondary')).toEqual([['Obliques'], ['Lats', 'Abs']])
  })

  it('clears a muscle tapped again in the same mode', () => {
    expect(mark(['Abs'], ['Lats'], 'Lats', 'secondary')).toEqual([['Abs'], []])
    expect(mark(['Abs'], ['Lats'], 'Abs', 'primary')).toEqual([[], ['Lats']])
  })
})

describe('markOf', () => {
  it('gives the strongest mark in a group', () => {
    expect(markOf(['Abs'], ['Serratus'], ['Abs', 'Serratus'])).toBe('primary')
    expect(markOf([], ['Serratus'], ['Abs', 'Serratus'])).toBe('secondary')
    expect(markOf(['Lats'], [], ['Abs', 'Serratus'])).toBe(null)
  })
})

describe('musclesOf', () => {
  it('lists Serratus with Core', () => {
    expect(musclesOf('Core')).toEqual(['Abs', 'Obliques', 'Transverse Abdominis', 'Serratus'])
    expect(musclesOf('Chest')).toEqual(['Upper Chest', 'Mid/Lower Chest'])
  })
})

describe('tapGroup', () => {
  it('marks every muscle of a group that does one job', () => {
    expect(tapGroup([], ['Lats'], 'Calves', 'primary')).toEqual([['Gastrocnemius', 'Soleus'], ['Lats']])
    expect(tapGroup(['Abs'], [], 'Chest', 'secondary')).toEqual([['Abs'], ['Upper Chest', 'Mid/Lower Chest']])
  })

  it('leaves a group of mixed jobs for the person to pick', () => {
    expect(tapGroup([], [], 'Shoulders', 'primary')).toEqual([[], []])
    expect(tapGroup([], [], 'Hips', 'primary')).toEqual([[], []])
  })

  it('changes nothing once a muscle of the group is marked', () => {
    expect(tapGroup(['Soleus'], [], 'Calves', 'primary')).toEqual([['Soleus'], []])
  })
})
