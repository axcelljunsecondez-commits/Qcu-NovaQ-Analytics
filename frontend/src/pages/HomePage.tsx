import { headingText } from '../lib/headingText'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { LanguageSelect } from '../components/layout/LanguageSelect'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { ExpandableSlides } from '../components/home/ExpandableSlides'
import { QueueTypesComparison } from '../components/home/QueueTypesComparison'
import { QueueingLessons } from '../components/learning/QueueingLessons'

const START_PATH = '/analyses/new'

// Public Home (spec §7.1, D5, D8). The only "Start an analysis" button is in the hero.
// Help (plan U8) and the Quick calculator (plan U9/B2) are public and linked from the header.
export function HomePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [howOpen, setHowOpen] = useState(false)
  const [queuesOpen, setQueuesOpen] = useState(false)
  const start = user ? START_PATH : `/login?next=${encodeURIComponent(START_PATH)}`

  return (
    <div className="home-page home-learning-page">
      <a className="skip-link" href="#home-main">{t('common.skip_to_content')}</a>
      <header className="home-header">
        <div className="home-logo">Nova<b>Q</b></div>
        <nav className="home-header-actions" aria-label={t('home.header_navigation')}>
          <button type="button" className="home-how-link" aria-expanded={howOpen} aria-controls="home-how-it-works-panel" onClick={() => setHowOpen(true)}>{t('home.how_it_works')}</button>
          <Link to="/calculator">{t('nav.quick_calculator')}</Link>
          <Link to="/help">{t('nav.help')}</Link>
          <LanguageSelect />
          <ThemeToggle />
          {user
            ? <Link className="btn-ghost home-header-link" to="/analyses">{t('home.go_to_analyses')}</Link>
            : <Link className="btn-ghost home-header-link" to="/login">{t('home.sign_in')}</Link>}
        </nav>
      </header>

      <main className="home-main home-spotlight" id="home-main">
        <div className="home-spotlight-column">
        <section className="home-hero" aria-labelledby="home-title">
          <p className="home-tagline">{t('nav.motto')}</p>
          <h1 lang="en" id="home-title">{headingText(t, 'home.hero_title')}<br /><span>{headingText(t, 'home.hero_accent')}</span></h1>
          <p>{t('home.hero_desc')}</p>
          <div className="home-hero-actions">
            <Link className="btn-primary home-start" to={start}>{t('home.start')}</Link>
            <Link className="btn-ghost" to="/calculator">{t('home.try_calculator')}</Link>
          </div>
          <p className="home-note">{t('home.calculator_note')}</p>
        </section>
        <ExpandableSlides id="home-how-it-works" title={headingText(t, 'home.how_it_works')} description={t('queueing101.how_description')}
          open={howOpen} onOpenChange={setHowOpen} slides={(['records', 'plans', 'watch'] as const).map((step, index) => ({
            id: step, label: t('queueing101.step', { number: index + 1 }), content: <div className="home-workflow-slide">
              <p className="home-slide-eyebrow">{t('queueing101.step', { number: index + 1 })}</p>
              <h3 lang="en">{headingText(t, `home.step_${step}_title`)}</h3><p>{t(`home.step_${step}_desc`)}</p>
            </div>,
          }))} />
        </div>
        <div className="home-spotlight-column">
          <QueueingLessons />
        </div>
        <QueueTypesComparison open={queuesOpen} onOpenChange={setQueuesOpen} />
      </main>

      <footer className="home-footer"><span>NovaQ v1.0 · {t('nav.capstone')}</span></footer>
    </div>
  )
}
