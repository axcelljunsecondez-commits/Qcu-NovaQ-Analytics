import { describe, expect, it } from 'vitest'
import { createInstance } from 'i18next'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'
import { headingText } from './headingText'
import { searchHelp } from './helpGuides'
import { matchingTutorials } from './tutorials'
import { generateOptimizationInsights } from './insights'

async function filipino() {
  const instance = createInstance()
  await instance.init({ lng: 'tl', fallbackLng: 'en', resources: { en: { translation: en }, tl: { translation: tl } } })
  return instance
}

describe('English headings with selected-language copy', () => {
  it('uses English only for the heading usage of a shared translation key', async () => {
    const instance = await filipino()
    expect(headingText(instance.t, 'nav.quick_calculator')).toBe('Quick Calculator')
    expect(instance.t('nav.quick_calculator')).toBe('Mabilisang Calculator')
    expect(instance.language).toBe('tl')
    const insight = generateOptimizationInsights(2, 3, null, null, null, instance.t)[0]
    expect(insight.title).toBe(en['insights.staffing_increase_title'])
    expect(insight.message).toBe(instance.t('insights.staffing_increase_message', { current: 2, recommended: 3 }))
  })

  it('preserves interpolated user names and overrides accidental language options', async () => {
    const instance = await filipino()
    const name = 'Pila ni María <test>'
    const title = headingText(instance.t, 'analyses.archive_confirm_title', { name, lng: 'tl', interpolation: { escapeValue: false } })
    expect(title).toContain(name)
    expect(title).toBe(instance.t('analyses.archive_confirm_title', { name, lng: 'en', interpolation: { escapeValue: false } }))
  })

  it('finds displayed English headings and Filipino title aliases with Filipino body text', async () => {
    const instance = await filipino()
    expect(searchHelp('Queue Simulation', instance.t)).toContainEqual({ topic: 'simulation', section: null, title: 'Queue Simulation' })
    expect(searchHelp(tl['help.guide.simulation.closing.title'], instance.t).some((match) => match.section === 'closing' && match.title.startsWith('Queue Simulation:'))).toBe(true)
    expect(searchHelp(tl['help.guide.results.title'], instance.t)).toContainEqual({ topic: 'results', section: null, title: 'Reading Results' })
    expect(matchingTutorials('Analysis Key Metric', instance.t).map((item) => item.id)).toContain('key-metrics')
  })
})
