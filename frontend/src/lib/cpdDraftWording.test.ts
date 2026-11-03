import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'

// A6 wording (C-PD / C-PD-C), approved by owner delegation on 2026-11-03: the catalogs must hold exactly the
// register's text (docs/wording/2026-11-02-cpd-a6-draft-wording.json), and every entry carries that status.

interface WordingEntry {
  key: string
  slot: string
  en: string
  tl: string
  source: string
  status: string
}

const register = JSON.parse(
  readFileSync(resolve(__dirname, '../../../docs/wording/2026-11-02-cpd-a6-draft-wording.json'), 'utf8'),
) as { entries: WordingEntry[] }
const catalogs: Record<'en' | 'tl', Record<string, string>> = { en, tl }

describe('A6 wording register', () => {
  it('lists the A6 keys once each, all approved by owner delegation on 2026-11-03', () => {
    expect(register.entries.map((entry) => entry.key)).toEqual([
      'simulation.current_too_large',
      'simulation.current_day_not_found',
      'simulation.current_day_mismatch',
      'simulation.current_all_dates_note',
      'simulation.current_zero_arrival_note_one',
      'simulation.current_zero_arrival_note_other',
      'charts.longest_take_current_date_one',
      'charts.longest_take_current_date_other',
    ])
    expect(register.entries.every((entry) => entry.status === 'approved_owner_delegated_2026-11-03')).toBe(true)
    expect(register.entries.every((entry) => entry.source.trim() !== '')).toBe(true)
  })

  it('keeps both catalogs equal to the register', () => {
    for (const entry of register.entries) {
      expect(catalogs.en[entry.key]).toBe(entry.en)
      expect(catalogs.tl[entry.key]).toBe(entry.tl)
    }
  })

  it('replaced the single N2 key with its plural pair', () => {
    expect(catalogs.en['simulation.current_zero_arrival_note']).toBeUndefined()
    expect(catalogs.tl['simulation.current_zero_arrival_note']).toBeUndefined()
  })

  it('keeps the placeholders the screens fill in, in both languages', () => {
    const needs: Record<string, string[]> = {
      'simulation.current_too_large': ['{{dates}}'],
      'simulation.current_all_dates_note': ['{{dates}}'],
      'simulation.current_zero_arrival_note_one': ['{{count}}'],
      'simulation.current_zero_arrival_note_other': ['{{count}}'],
      'charts.longest_take_current_date_one': ['{{date}}', '{{count}}', '{{where}}'],
      'charts.longest_take_current_date_other': ['{{date}}', '{{count}}', '{{where}}'],
    }
    for (const [key, placeholders] of Object.entries(needs)) {
      for (const placeholder of placeholders) {
        expect(catalogs.en[key]).toContain(placeholder)
        expect(catalogs.tl[key]).toContain(placeholder)
      }
    }
  })
})
