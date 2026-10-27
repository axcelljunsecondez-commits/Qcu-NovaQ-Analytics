import type { TFunction, TOptions } from 'i18next'

/** Built-in headings stay English; body copy and shared keys keep the selected language. */
export function headingText(t: TFunction, key: string, options?: TOptions): string {
  return t(key, { ...options, lng: 'en', returnObjects: false, returnDetails: false })
}
