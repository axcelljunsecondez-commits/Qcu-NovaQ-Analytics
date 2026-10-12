import type { TFunction } from 'i18next'

// Help center guides (spec 2026-10-09 §7.11, plan U8). Text lives in the locale files under
// help.guide.<topic>.*; each guide states its action, purpose and next step, then its sections.
// Every guide is public: none holds account data.
export const HELP_GUIDES = [
  { topic: 'start', sections: ['create', 'structure'] },
  { topic: 'data', sections: ['template', 'upload', 'purpose', 'read', 'advanced'] },
  { topic: 'results', sections: ['estimated', 'levels', 'plan', 'older'] },
  { topic: 'plans', sections: ['make', 'use'] },
  { topic: 'simulation', sections: ['pages', 'methods', 'closing', 'reading', 'service', 'breaks'] },
  { topic: 'checks', sections: ['checks', 'decision'] },
  { topic: 'downloads', sections: ['reports'] },
  { topic: 'problems', sections: ['upload', 'stale', 'rate', 'signin'] },
] as const

export type HelpTopic = (typeof HELP_GUIDES)[number]['topic']

export function isHelpTopic(value: string | undefined): value is HelpTopic {
  return HELP_GUIDES.some((guide) => guide.topic === value)
}

export interface HelpMatch {
  topic: HelpTopic
  section: string | null
  title: string
}

/** Guides and sections whose text, in the current language, contains every word of the query. */
export function searchHelp(query: string, t: TFunction): HelpMatch[] {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return []
  const has = (text: string) => {
    const lower = text.toLocaleLowerCase()
    return words.every((word) => lower.includes(word))
  }
  const matches: HelpMatch[] = []
  for (const guide of HELP_GUIDES) {
    const base = `help.guide.${guide.topic}`
    const guideTitle = t(`${base}.title`)
    if (has([guideTitle, t(`${base}.action`), t(`${base}.purpose`), t(`${base}.next`)].join(' '))) {
      matches.push({ topic: guide.topic, section: null, title: guideTitle })
    }
    for (const section of guide.sections) {
      const title = t(`${base}.${section}.title`)
      if (has(`${title} ${t(`${base}.${section}.body`)}`)) matches.push({ topic: guide.topic, section, title: `${guideTitle}: ${title}` })
    }
  }
  return matches
}
