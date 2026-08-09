import { useTranslation } from 'react-i18next'
import { setLang } from '../../lib/i18n'

export function LanguageSelector() {
  const { i18n } = useTranslation()
  const current = i18n.language === 'tl' ? 'tl' : 'en'
  return (
    <div className="sidebar-section">
      <button
        type="button"
        className={`lang-btn${current === 'en' ? ' active' : ''}`}
        onClick={() => setLang('en')}
      >
        🇺🇸 English
      </button>
      <button
        type="button"
        className={`lang-btn${current === 'tl' ? ' active' : ''}`}
        onClick={() => setLang('tl')}
      >
        🇵🇭 Filipino
      </button>
    </div>
  )
}
