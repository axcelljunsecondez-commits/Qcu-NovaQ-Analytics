import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { matchingQueueingLessons, videoTime, type QueueingLessonId } from '../../lib/queueingLessons'
import { CollectionChecklist } from './CollectionChecklist'
import { LessonPlayer } from './LessonPlayer'
import '../../styles/queueing101.css'

/** Shared by the public homepage and Help; changes no account or analysis state. */
export function QueueingLessons({ query = '' }: { query?: string }) {
  const { t } = useTranslation()
  const titleId = useId()
  const items = matchingQueueingLessons(query, t)
  const [selected, setSelected] = useState<QueueingLessonId>('part1')
  const lesson = items.find((item) => item.id === selected) ?? items[0]
  useEffect(() => { if (lesson && lesson.id !== selected) setSelected(lesson.id) }, [lesson, selected])
  if (!lesson) return null
  return <section className="queueing-lessons" aria-labelledby={titleId}>
    <p className="queueing-eyebrow">{t('queueing101.title')}</p>
    <h2 id={titleId}>{t('queueing101.start_here')}</h2>
    <p className="queueing-lessons-intro">{t('queueing101.introduction')}</p>
    <div className="queueing-lesson-card">
      <LessonPlayer key={lesson.id} lesson={lesson} />
      <div className="queueing-lesson-choices" role="group" aria-label={t('queueing101.choose')}>
        {items.map((item) => <button key={item.id} type="button" className="queueing-lesson-choice" aria-pressed={item.id === lesson.id} onClick={() => setSelected(item.id)}>
          <span className="queueing-lesson-number" aria-hidden="true">{item.id === 'part1' ? '1' : '2'}</span>
          <span><strong>{t(`queueing101.${item.id}.title`)}</strong><small>{t(`queueing101.${item.id}.description`)}</small><small className="queueing-lesson-topics">{t(`queueing101.${item.id}.topics`)}</small><small>{videoTime(item.seconds)}</small></span>
        </button>)}
      </div>
      <div className="queueing-collection"><CollectionChecklist /></div>
    </div>
    <p className="queueing-language-note">{t('queueing101.language')}</p>
    <p className="queueing-example-note">{t('queueing101.example_note')}</p>
  </section>
}
