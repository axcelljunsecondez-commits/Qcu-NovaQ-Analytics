import type { TFunction } from 'i18next'
import { headingText } from './headingText'
import steps from './tutorialSteps.json'

export const TUTORIALS = [
  { id: 'analysis-workflow', seconds: 62, bytes: 1387977, sha256: '5a27b75e8e02b7a651804404341e3d68990275752e27573c6d0c6874b85be62a', revision: '5a27b75e8e02' },
  { id: 'key-metrics', seconds: 91, bytes: 3664985, sha256: '78ed2acb4af253902ee1d2dfffd1080520c600c2a42175cc432d9de5f800b5ff', revision: '78ed2acb4af2' },
  { id: 'queue-simulation', seconds: 145, bytes: 5112569, sha256: '9cc2158fdb7da46f00795b0adc16a9608bc3446f99a8903c2efaca483a0ad370', revision: '9cc2158fdb7d' },
] as const

export type TutorialId = (typeof TUTORIALS)[number]['id']
export type Tutorial = (typeof TUTORIALS)[number]

export function tutorialFile(tutorial: Tutorial, extension: 'mp4' | 'vtt' | 'webp'): string {
  return `/tutorials/${tutorial.id}.${extension}?v=${tutorial.revision}`
}

export function tutorialDuration(tutorial: Tutorial): string {
  return `${Math.floor(tutorial.seconds / 60)}:${String(tutorial.seconds % 60).padStart(2, '0')}`
}

export function tutorialSteps(id: TutorialId): Array<{ time: string; caption: string }> {
  return steps[id]
}

export function matchingTutorials(query: string, t: TFunction): Tutorial[] {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return TUTORIALS.filter((item) => {
    const text = `${headingText(t, `tutorials.${item.id}.title`)} ${t(`tutorials.${item.id}.title`)} ${t(`tutorials.${item.id}.description`)}`.toLocaleLowerCase()
    return words.every((word) => text.includes(word))
  })
}
