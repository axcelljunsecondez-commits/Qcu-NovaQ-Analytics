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

export type HelpLanguage = 'en' | 'tl'

export interface HelpFigure {
  /** Numbered outlines in the picture, listed in help.guide.<topic>.figure_mark_<n>. */
  marks: number
  /** Captured width and height in pixels, per language. */
  size: Record<HelpLanguage, readonly [number, number]>
}

// Annotated screenshots (plan U10): public/help-images/<lang>/<topic>.webp, taken by
// scripts/help-screenshots.mjs from a scratch app with clearly synthetic data. Problems has none:
// it covers several screens.
export const HELP_FIGURES: Partial<Record<HelpTopic, HelpFigure>> = {
  start: { marks: 3, size: { en: [1080, 787], tl: [1080, 808] } },
  data: { marks: 3, size: { en: [1080, 695], tl: [1080, 737] } },
  results: { marks: 3, size: { en: [1080, 666], tl: [1080, 730] } },
  plans: { marks: 3, size: { en: [1080, 922], tl: [1080, 1004] } },
  simulation: { marks: 4, size: { en: [1080, 777], tl: [1080, 830] } },
  checks: { marks: 3, size: { en: [1080, 572], tl: [1080, 614] } },
  downloads: { marks: 4, size: { en: [1080, 981], tl: [1080, 1002] } },
}

export function helpFigureSrc(topic: HelpTopic, language: HelpLanguage): string {
  return `/help-images/${language}/${topic}.webp`
}

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
