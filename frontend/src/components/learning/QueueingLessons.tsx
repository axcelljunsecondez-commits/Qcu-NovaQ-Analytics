import { headingText } from '../../lib/headingText'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { matchingQueueingLessons, videoTime } from '../../lib/queueingLessons'
import { CollectionChecklist } from './CollectionChecklist'
import { LessonPlayer } from './LessonPlayer'
import '../../styles/queueing101.css'

/** Shared by the public homepage and Help; changes no account or analysis state. */
export function QueueingLessons({ query = '' }: { query?: string }) {
  const { t } = useTranslation()
  const titleId = useId()
  const lesson = matchingQueueingLessons(query, t)[0]
  if (!lesson) return null
  return <section className="queueing-lessons" aria-labelledby={titleId}>
    <p className="queueing-eyebrow">{t('queueing101.title')}</p>
    <h2 lang="en" id={titleId}>{headingText(t, 'queueing101.start_here')}</h2>
    <p className="queueing-lessons-intro">{t('queueing101.introduction')}</p>
    <div className="queueing-lesson-card">
      <LessonPlayer key={lesson.id} lesson={lesson} />
      <div className="queueing-combined-description">
        <div className="queueing-combined-title"><h3 lang="en">{headingText(t, 'queueing101.combined.title')}</h3><span className="queueing-combined-duration">{videoTime(Math.round(lesson.seconds))}</span></div>
        <p>{t('queueing101.combined.description')}</p>
        <p className="queueing-lesson-topics">{t('queueing101.combined.topics')}</p>
      </div>
      <div className="queueing-collection"><CollectionChecklist /></div>
    </div>
    <p className="queueing-language-note">{t('queueing101.combined.language')}</p>
    <p className="queueing-example-note">{t('queueing101.example_note')}</p>
  </section>
}
