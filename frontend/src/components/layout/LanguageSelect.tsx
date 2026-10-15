import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { setLang } from '../../lib/i18n'

// Labelled language dropdown for public and sign-in pages (spec §7.2, §10).
export function LanguageSelect() {
  const { t, i18n } = useTranslation()
  const id = useId()
  return (
    <div className="language-select">
      <label htmlFor={id}>{t('language.label')}</label>
      <select id={id} value={i18n.language === 'tl' ? 'tl' : 'en'} onChange={(event) => setLang(event.target.value === 'tl' ? 'tl' : 'en')}>
        <option value="en">English</option>
        <option value="tl">Filipino</option>
      </select>
    </div>
  )
}
