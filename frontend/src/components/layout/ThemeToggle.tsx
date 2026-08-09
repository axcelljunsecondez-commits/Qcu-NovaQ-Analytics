import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

const THEME_KEY = 'novamart_theme'

export function ThemeToggle() {
  const { t } = useTranslation()
  const isDark = document.documentElement.dataset.theme === 'dark'

  useEffect(() => {
    document.documentElement.dataset.theme = isDark ? 'dark' : 'light'
  }, [isDark])

  function toggle() {
    const next = isDark ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    if (next === 'dark') {
      localStorage.setItem(THEME_KEY, 'dark')
    } else {
      localStorage.removeItem(THEME_KEY)
    }
  }

  return (
    <button type="button" className="btn-ghost theme-toggle" onClick={toggle}>
      {isDark ? t('theme.light') : t('theme.dark')}
    </button>
  )
}
