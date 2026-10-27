import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'

interface RecordEntry {
  key: string
  language: 'en' | 'tl'
  before: string
  requested: string
  applied: string
  status: string
  reason: string
}
const report = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/wording/2026-10-27-local-wording-application.json'), 'utf8')) as { records: RecordEntry[] }
const catalogs: Record<string, Record<string, string>> = { en, tl }

describe('Approved PDF wording', () => {
  it('matches every mapped submission or explicitly retains a documented semantic conflict', () => {
    expect(report.records.length).toBe(200)
    for (const record of report.records) {
      expect(catalogs[record.language][record.key], `${record.language}:${record.key}`).toBe(record.applied)
      if (record.status === 'retained_conflict') {
        expect(record.reason).not.toBe('')
        expect(record.applied).toBe(record.before)
      } else expect(record.applied).toBe(record.requested)
      expect(record.applied.match(/{{.*?}}/g)).toEqual(record.before.match(/{{.*?}}/g))
    }
  })

  it('preserves the submitted conceptual Filipino and screenshot-independent hours', () => {
    expect(tl['home.step_records_desc']).toBe('Mag-upload ng mga rekord ng customer o bilang bawat panahon (period), gamit ang CSV o Excel template ng NovaQ.')
    expect(tl['home.step_watch_desc']).toBe('I-replay ang pagdating, paghihintay, at paglilingkod sa mga customer.')
    expect(en['simulation.operating_hours']).toBe('Operating hours: {{hours}}.')
    expect(en['home.hero_title'] + ' ' + en['home.hero_accent']).toBe('Smarter Staffing, Shorter Queues.')
  })
})
