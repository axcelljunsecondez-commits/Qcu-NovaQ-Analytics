import { headingText } from '../lib/headingText'
import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { VideoTutorials } from '../components/help/VideoTutorials'
import { matchingTutorials } from '../lib/tutorials'
import { QueueingLessons } from '../components/learning/QueueingLessons'
import { matchingQueueingLessons } from '../lib/queueingLessons'
import { HELP_FIGURES, HELP_GUIDES, helpFigureSrc, isHelpTopic, searchHelp } from '../lib/helpGuides'

// Help center (spec 2026-10-09 §7.11, plan U8): search over the guides in the current language,
// one page per guide at /help/:topic, and #section anchors for the "?" links on other screens.
export function HelpPage() {
  const { topic } = useParams()
  if (topic === undefined) return <HelpIndex />
  if (!isHelpTopic(topic)) return <Navigate to="/help" replace />
  return <HelpGuide topic={topic} />
}

function HelpIndex() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const matches = searchHelp(query, t)
  const videoMatches = matchingTutorials(query, t)
  const queueingMatches = matchingQueueingLessons(query, t)
  return (
    <div className="page-stack help-page">
      <header className="page-header">
        <p className="topbar-eyebrow">{t('help.eyebrow')}</p>
        <h1 lang="en" className="page-title">{headingText(t, 'help.title')}</h1>
        <p className="page-caption">{t('help.subtitle')}</p>
      </header>

      <section className="card" role="search">
        <label lang="en" htmlFor="help-search" className="card-title">{headingText(t, 'help.search_label')}</label>
        <input id="help-search" type="search" value={query} placeholder={t('help.search_placeholder')}
          onChange={(event) => setQuery(event.target.value)} />
        {query.trim() && (
          matches.length > 0 ? (
            <ul className="help-results" aria-label={t('help.search_results')}>
              {matches.map((match) => (
                <li key={`${match.topic}-${match.section ?? ''}`}>
                  <Link to={`/help/${match.topic}${match.section ? `#${match.section}` : ''}`}>{match.title}</Link>
                </li>
              ))}
            </ul>
          ) : videoMatches.length === 0 && queueingMatches.length === 0 ? <p className="form-hint" role="status">{t('help.search_none')}</p> : null
        )}
      </section>

      <QueueingLessons query={query} />
      <VideoTutorials query={query} />

      <section aria-labelledby="help-guides-title">
        <h2 lang="en" id="help-guides-title" className="section-title">{headingText(t, 'help.guides_title')}</h2>
        <ul className="help-guide-list">
          {HELP_GUIDES.map((guide) => (
            <li key={guide.topic} className="card">
              <h3 lang="en" className="card-title"><Link to={`/help/${guide.topic}`}>{headingText(t, `help.guide.${guide.topic}.title`)}</Link></h3>
              <p>{t(`help.guide.${guide.topic}.purpose`)}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby="help-preferences-title">
        <h2 lang="en" id="help-preferences-title" className="card-title">{headingText(t, 'help.preferences_title')}</h2>
        <p>{t('help.preferences_desc')}</p>
        <Link className="button-link" to="/settings/preferences">{t('help.open_preferences')}</Link>
      </section>

      <section className="card" aria-labelledby="help-limits-title">
        <h2 lang="en" id="help-limits-title" className="card-title">{headingText(t, 'help.limits_title')}</h2>
        <p>{t('help.limits_desc')}</p>
      </section>
    </div>
  )
}

function HelpGuide({ topic }: { topic: (typeof HELP_GUIDES)[number]['topic'] }) {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const guide = HELP_GUIDES.find((item) => item.topic === topic)!
  const base = `help.guide.${topic}`
  const figure = HELP_FIGURES[topic]
  const language = i18n.language === 'tl' ? 'tl' : 'en'

  useEffect(() => {
    // Deep links such as /help/simulation#closing open at that section.
    const id = decodeURIComponent(location.hash.slice(1))
    if (id) document.getElementById(id)?.scrollIntoView({ block: 'start' })
  }, [location.hash, topic])

  return (
    <article className="page-stack help-page" aria-labelledby="help-guide-title">
      <nav aria-label={t('nav.breadcrumb')}><Link to="/help">{t('help.all_guides')}</Link></nav>
      <header className="page-header">
        <p className="topbar-eyebrow">{t('help.eyebrow')}</p>
        <h1 lang="en" id="help-guide-title" className="page-title">{headingText(t, `${base}.title`)}</h1>
      </header>
      <section className="card help-summary">
        <dl>
          <dt>{t('help.action')}</dt><dd>{t(`${base}.action`)}</dd>
          <dt>{t('help.purpose')}</dt><dd>{t(`${base}.purpose`)}</dd>
          <dt>{t('help.next_step')}</dt><dd>{t(`${base}.next`)}</dd>
        </dl>
      </section>
      {figure && (
        <figure className="card help-figure">
          <img src={helpFigureSrc(topic, language)} alt={t(`${base}.figure_alt`)}
            width={figure.size[language][0]} height={figure.size[language][1]} loading="lazy" />
          <figcaption>
            <p className="form-hint">{t('help.figure_note')}</p>
            <ol>
              {Array.from({ length: figure.marks }, (_, index) => (
                <li key={index}>{t(`${base}.figure_mark_${index + 1}`)}</li>
              ))}
            </ol>
          </figcaption>
        </figure>
      )}
      {guide.sections.map((section) => (
        <section key={section} id={section} className="card" aria-labelledby={`help-${section}-title`}>
          <h2 lang="en" id={`help-${section}-title`} className="card-title">{headingText(t, `${base}.${section}.title`)}</h2>
          <p>{t(`${base}.${section}.body`)}</p>
        </section>
      ))}
    </article>
  )
}
