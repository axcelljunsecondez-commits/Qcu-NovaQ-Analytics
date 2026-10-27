import { headingText } from '../../lib/headingText'
import { useTranslation } from 'react-i18next'
import { matchingTutorials, tutorialDuration, tutorialFile } from '../../lib/tutorials'
import { TutorialWatch } from './TutorialWatch'

export function VideoTutorials({ query }: { query: string }) {
  const { t } = useTranslation()
  const items = matchingTutorials(query, t)
  if (items.length === 0) return null
  return <section className="tutorial-library" aria-labelledby="video-tutorials-title">
    <div className="tutorial-section-heading"><h2 lang="en" id="video-tutorials-title" className="section-title">{headingText(t, 'tutorials.title')}</h2><p className="form-hint">{t('tutorials.language')}</p></div>
    <ul className="tutorial-grid">
      {items.map((item) => <li key={item.id} className="card tutorial-card">
        <img src={tutorialFile(item, 'webp')} width={800} height={450} loading="lazy" alt="" />
        <div className="tutorial-card-content">
          <h3 lang="en" className="card-title">{headingText(t, `tutorials.${item.id}.title`)}</h3>
          <p className="form-hint">{tutorialDuration(item)} · {(item.bytes / 1024 ** 2).toFixed(2)} MiB</p>
          <p>{t(`tutorials.${item.id}.description`)}</p>
          <div className="tutorial-card-actions"><TutorialWatch id={item.id} compact /><a href={tutorialFile(item, 'mp4')} download={`${item.id}.mp4`}>{t('tutorials.download')}</a></div>
        </div>
      </li>)}
    </ul>
  </section>
}
