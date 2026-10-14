import { readStorage, writeStorage } from './safeStorage'

export const THEME_KEY = 'novaq_theme'
export type Theme = 'light' | 'dark'

const listeners = new Set<() => void>()

export function savedTheme(): Theme {
  return readStorage(THEME_KEY) === 'dark' ? 'dark' : 'light'
}

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  writeStorage(THEME_KEY, theme)
  listeners.forEach((listener) => listener())
}

// Every theme control reads the same document state, so two controls on one
// screen (header and Settings → Appearance) never disagree.
export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
