import { describe, expect, it } from 'vitest'
import { isCompound } from './compound'

describe('isCompound', () => {
  it('is compound when two or more joints move', () => {
    expect(isCompound(['hip extension', 'knee extension'])).toBe(true)
    expect(isCompound(['shoulder adduction', 'elbow flexion', 'shoulder blade depression'])).toBe(true)
  })

  it('is isolation when one joint moves', () => {
    expect(isCompound(['elbow flexion'])).toBe(false)
  })

  it('counts the shoulder blade with the shoulder and the forearm with the elbow', () => {
    expect(isCompound(['shoulder abduction', 'shoulder blade upward rotation'])).toBe(false)
    expect(isCompound(['elbow flexion', 'forearm supination'])).toBe(false)
  })

  it('is not known without joint movements', () => {
    expect(isCompound([])).toBe(null)
  })
})
