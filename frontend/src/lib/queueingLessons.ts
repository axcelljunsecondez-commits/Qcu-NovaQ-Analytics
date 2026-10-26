import type { TFunction } from 'i18next'
import content from './queueingLessonContent.json'

export const QUEUEING_LESSON_IDS = ['part1', 'part2'] as const
export type QueueingLessonId = typeof QUEUEING_LESSON_IDS[number]
export type QueueingLesson = { id: QueueingLessonId } & typeof content.part1
export const QUEUEING_LESSONS: QueueingLesson[] = QUEUEING_LESSON_IDS.map((id) => ({ id, ...content[id] }))

export function queueingLessonAsset(lesson: QueueingLesson, extension: 'mp4' | 'vtt' | 'webp'): string {
  return `/queueing101/${lesson.id}.${extension}?v=${lesson.revision}`
}

export function matchingQueueingLessons(query: string, t: TFunction): QueueingLesson[] {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return QUEUEING_LESSONS.filter(({ id }) => {
    const text = `${t('queueing101.title')} ${t(`queueing101.${id}.title`)} ${t(`queueing101.${id}.description`)} ${t(`queueing101.${id}.topics`)} ${t(`queueing101.${id}.search_terms`)}`.toLocaleLowerCase()
    return words.every((word) => text.includes(word))
  })
}

export function videoTime(seconds: number): string {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  return `${Math.floor(safe / 60)}:${String(Math.floor(safe % 60)).padStart(2, '0')}`
}
