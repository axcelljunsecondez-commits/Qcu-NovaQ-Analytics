import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

const THEME_KEY = 'novaq_theme'

function initialTheme() {
  return document.documentElement.dataset.theme === 'dark' || localStorage.getItem(THEME_KEY) === 'dark'
}

export function ThemeToggle() {
  const { t } = useTranslation()
  const [isDark, setIsDark] = useState(initialTheme)

  useEffect(() => {
    const theme = isDark ? 'dark' : 'light'
    document.documentElement.dataset.theme = theme
    localStorage.setItem(THEME_KEY, theme)
  }, [isDark])

  return (
    <button type="button" className="btn-ghost theme-toggle" aria-pressed={isDark} onClick={() => setIsDark((value) => !value)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d={isDark ? 'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z' : 'M21 15.2A9 9 0 0 1 8.8 3 9 9 0 1 0 21 15.2Z'} /></svg>
      <span>{isDark ? t('theme.light') : t('theme.dark')}</span>
    </button>
  )
}
