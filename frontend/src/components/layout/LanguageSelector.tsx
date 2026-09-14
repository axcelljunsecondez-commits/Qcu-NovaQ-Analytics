import { useTranslation } from 'react-i18next'
import { setLang } from '../../lib/i18n'

export function LanguageSelector() {
  const { i18n } = useTranslation()
  const current = i18n.language === 'tl' ? 'tl' : 'en'
  return (
    <div className="sidebar-section language-selector" role="group" aria-label={i18n.t('language.label')}>
      <button
        type="button"
        className={`lang-btn${current === 'en' ? ' active' : ''}`}
        aria-pressed={current === 'en'}
        onClick={() => setLang('en')}
      >
        <span aria-hidden="true">EN</span> English
      </button>
      <button
        type="button"
        className={`lang-btn${current === 'tl' ? ' active' : ''}`}
        aria-pressed={current === 'tl'}
        onClick={() => setLang('tl')}
      >
        <span aria-hidden="true">TL</span> Filipino
      </button>
    </div>
  )
}
