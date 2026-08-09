import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'

export const LANG_KEY = 'novamart_lang'

export function initI18n(): void {
  const saved = localStorage.getItem(LANG_KEY)
  void i18n.use(initReactI18next).init({
    resources: {
      en: { translation: en },
      tl: { translation: tl },
    },
    lng: saved === 'tl' ? 'tl' : 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })
}

export function setLang(lang: 'en' | 'tl'): void {
  void i18n.changeLanguage(lang)
  localStorage.setItem(LANG_KEY, lang)
}
