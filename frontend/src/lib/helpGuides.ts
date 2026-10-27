import type { TFunction } from 'i18next'
import { headingText } from './headingText'

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

// Annotated screenshots (plan U10): public/help-images/<lang>/<topic>.webp. The October 27
// recapture used isolated synthetic browser fixtures; see docs/wording/2026-10-27-local-wording-report.md.
// scripts/help-screenshots.mjs also supports a scratch app. Problems covers several screens and has no image.
export const HELP_FIGURES: Partial<Record<HelpTopic, HelpFigure>> = {
  start: { marks: 3, size: { en: [1080, 808], tl: [1080, 808] } },
  data: { marks: 3, size: { en: [1080, 653], tl: [1080, 674] } },
  results: { marks: 3, size: { en: [1080, 1158], tl: [1080, 1182] } },
  plans: { marks: 3, size: { en: [1080, 1678], tl: [1080, 1741] } },
  simulation: { marks: 4, size: { en: [1080, 631], tl: [1080, 684] } },
  checks: { marks: 3, size: { en: [1080, 357], tl: [1080, 399] } },
  downloads: { marks: 4, size: { en: [1080, 955], tl: [1080, 955] } },
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
    const guideTitle = headingText(t, `${base}.title`)
    if (has([guideTitle, t(`${base}.title`), t(`${base}.action`), t(`${base}.purpose`), t(`${base}.next`)].join(' '))) {
      matches.push({ topic: guide.topic, section: null, title: guideTitle })
    }
    for (const section of guide.sections) {
      const title = headingText(t, `${base}.${section}.title`)
      if (has(`${title} ${t(`${base}.${section}.title`)} ${t(`${base}.${section}.body`)}`)) matches.push({ topic: guide.topic, section, title: `${guideTitle}: ${title}` })
    }
  }
  return matches
}
