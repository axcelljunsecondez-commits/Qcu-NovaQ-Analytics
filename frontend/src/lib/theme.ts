import { writeStorage } from './safeStorage'

export const THEME_KEY = 'novaq_theme'

/** Apply the owner-approved light interface before rendering, including old saved dark preferences. */
export function initializeTheme(): void {
  document.documentElement.dataset.theme = 'light'
  document.documentElement.style.colorScheme = 'light'
  writeStorage(THEME_KEY, 'light')
}
