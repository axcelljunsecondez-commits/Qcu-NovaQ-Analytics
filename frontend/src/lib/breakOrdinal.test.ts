import { describe, expect, it } from 'vitest'
import { testI18n } from '../test/test-utils'
import { breakOrdinal, breakOrdinalText } from './breakOrdinal'

// Phase D (owner-authorized 2026-11-25): server labels are "Break N" (break_optimization.py:229-233).

describe('breakOrdinal', () => {
  it('reads the order only from an exact "Break N" label with N >= 1', () => {
    expect(breakOrdinal('Break 1')).toBe(1)
    expect(breakOrdinal('Break 6')).toBe(6)
    expect(breakOrdinal('Break 111')).toBe(111)
    for (const label of ['Break 0', 'Break 01', 'Extra', 'break 1', 'Break 1 ', 'Break', 'Break -1', 'Break 1.5', '']) {
      expect(breakOrdinal(label), label).toBeNull()
    }
  })
})

describe('breakOrdinalText', () => {
  const i18n = testI18n()
  const en = i18n.getFixedT('en')
  const tl = i18n.getFixedT('tl')

  it('uses the owner words for the first five breaks', () => {
    expect([1, 2, 3, 4, 5].map((n) => breakOrdinalText(en, n))).toEqual(['1st break', '2nd break', '3rd break', '4th break', '5th break'])
    expect([1, 2, 3, 4, 5].map((n) => breakOrdinalText(tl, n))).toEqual(['Unang break', 'Ikalawang break', 'Ikatlong break', 'Ikaapat na break', 'Ikalimang break'])
  })

  it('resolves English ordinal suffixes through i18next plural rules from the 6th break on', () => {
    const cases: [number, string][] = [
      [6, '6th'], [11, '11th'], [12, '12th'], [13, '13th'], [21, '21st'], [22, '22nd'], [23, '23rd'], [24, '24th'], [101, '101st'], [111, '111th'], [112, '112th'],
    ]
    for (const [n, word] of cases) expect(breakOrdinalText(en, n), String(n)).toBe(`${word} break`)
  })

  it('uses "Ika-N na" in Tagalog from the 6th break on', () => {
    expect(breakOrdinalText(tl, 6)).toBe('Ika-6 na break')
    expect(breakOrdinalText(tl, 11)).toBe('Ika-11 na break')
    expect(breakOrdinalText(tl, 21)).toBe('Ika-21 na break')
  })
})
