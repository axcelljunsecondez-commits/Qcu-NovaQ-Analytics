import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { LineStructurePicture } from '../components/illustrations/LineStructurePicture'
import { LanguageSelect } from '../components/layout/LanguageSelect'
import { ThemeToggle } from '../components/layout/ThemeToggle'

const START_PATH = '/analyses/new'

// Public Home (spec §7.1, D5, D8). The only "Start an analysis" button is in the hero.
// Help is public (plan U8); Quick calculator joins the header when it becomes public (plan U9/B2).
export function HomePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const start = user ? START_PATH : `/login?next=${encodeURIComponent(START_PATH)}`

  return (
    <div className="home-page">
      <a className="skip-link" href="#home-main">{t('common.skip_to_content')}</a>
      <header className="home-header">
        <div className="home-logo">Nova<b>Q</b></div>
        <nav className="home-header-actions" aria-label={t('home.header_navigation')}>
          <a href="#how-it-works">{t('home.how_it_works')}</a>
          <Link to="/help">{t('nav.help')}</Link>
          <LanguageSelect />
          <ThemeToggle />
          {user
            ? <Link className="btn-ghost home-header-link" to="/analyses">{t('home.go_to_analyses')}</Link>
            : <Link className="btn-ghost home-header-link" to="/login">{t('home.sign_in')}</Link>}
        </nav>
      </header>

      <main className="home-main" id="home-main">
        <section className="home-hero" aria-labelledby="home-title">
          <h1 id="home-title">{t('home.hero_title')}<br /><span>{t('home.hero_accent')}</span></h1>
          <p>{t('home.hero_desc')}</p>
          <Link className="btn-primary home-start" to={start}>{t('home.start')}</Link>
        </section>

        <section className="home-structures" aria-labelledby="home-structures-title">
          <h2 id="home-structures-title">{t('home.structures_title')}</h2>
          <div className="home-structure-grid">
            {(['shared', 'separate'] as const).map((variant) => (
              <article key={variant} className="card home-structure-card">
                <LineStructurePicture variant={variant} />
                <h3>{t(`home.structure_${variant}_title`)}</h3>
                <p>{t(`home.structure_${variant}_desc`)}</p>
                <p className="home-note">{t(`home.structure_${variant}_example`)}</p>
              </article>
            ))}
          </div>
          <p className="home-note">{t('home.pictures_note')}</p>
        </section>

        <section className="home-steps" id="how-it-works" aria-labelledby="home-steps-title">
          <h2 id="home-steps-title">{t('home.how_it_works')}</h2>
          <ol>
            {(['records', 'plans', 'watch'] as const).map((step) => (
              <li key={step} className="card">
                <strong>{t(`home.step_${step}_title`)}</strong>
                <span>{t(`home.step_${step}_desc`)}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="home-footer"><span>NovaQ v1.0 · {t('nav.capstone')}</span><span>{t('nav.motto')}</span></footer>
    </div>
  )
}
