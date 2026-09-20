import { describe, expect, it } from 'vitest'
import enRaw from '../../public/locales/en/translation.json?raw'
import tlRaw from '../../public/locales/tl/translation.json?raw'

// JSON.parse silently keeps the last of two identical keys, so the catalogues have to be
// checked as raw text: a duplicate makes the earlier value dead and edits to it do nothing.
const CATALOGUES: [string, string][] = [['en', enRaw], ['tl', tlRaw]]

function declaredKeys(raw: string): string[] {
  return [...raw.matchAll(/^ {2}"([^"]+)"\s*:/gm)].map((match) => match[1])
}

describe('translation catalogues', () => {
  for (const [locale, raw] of CATALOGUES) {
    it(`declares every ${locale} key exactly once`, () => {
      const keys = declaredKeys(raw)
      const duplicates = [...new Set(keys.filter((key, index) => keys.indexOf(key) !== index))]
      expect(duplicates).toEqual([])
      // Guards the regex itself: every key the parser sees must have been extracted above,
      // otherwise a reformatted catalogue would pass this test without being checked.
      expect(new Set(keys).size).toBe(Object.keys(JSON.parse(raw) as Record<string, string>).length)
    })
  }

  it('keeps en and tl on the same key set', () => {
    const [en, tl] = CATALOGUES.map(([, raw]) => new Set(declaredKeys(raw)))
    expect([...en].filter((key) => !tl.has(key))).toEqual([])
    expect([...tl].filter((key) => !en.has(key))).toEqual([])
  })
})
