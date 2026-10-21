import type { TFunction } from 'i18next'
import steps from './tutorialSteps.json'

export const TUTORIALS = [
  { id: 'analysis-workflow', seconds: 255, bytes: 1973500, sha256: '8495ebfe3a0c992321126225079fbe3779107ae49ddd477b8a8ca54d9b549b3e', revision: '8495ebfe3a0c' },
  { id: 'key-metrics', seconds: 153, bytes: 1470909, sha256: '6be08abb6cc290f5b771a7320f2c7df156235836102e9eb1823fea7358f4ab56', revision: '6be08abb6cc2' },
  { id: 'queue-simulation', seconds: 246, bytes: 1780480, sha256: '9899542501e8aa09c8be280627650260598389bb0b836c19563e20d51001a786', revision: '9899542501e8' },
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
    const text = `${t(`tutorials.${item.id}.title`)} ${t(`tutorials.${item.id}.description`)}`.toLocaleLowerCase()
    return words.every((word) => text.includes(word))
  })
}
