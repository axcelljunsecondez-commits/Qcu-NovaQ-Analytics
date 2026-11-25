import type { TFunction } from 'i18next'

/**
 * Break order of a recorded break move (Phase D, owner-authorized 2026-11-25).
 * The server labels each cashier's recorded breaks "Break 1", "Break 2", ... in start order
 * (backend/queueing_engine/services/break_optimization.py). Any other label has no known order: null.
 * Display only; nothing here changes which moves exist or their order.
 */
const LABEL = /^Break ([1-9]\d*)$/

export function breakOrdinal(label: string): number | null {
  const match = LABEL.exec(label)
  if (!match) return null
  const value = Number(match[1])
  return Number.isSafeInteger(value) ? value : null
}

/** "1st break" / "Unang break"; words come from the locale files only. */
export function breakOrdinalText(t: TFunction, n: number): string {
  const ordinal = n <= 5 ? t(`supervisor.break_ordinal_word_${n}`) : t('supervisor.break_ordinal_word', { count: n, ordinal: true })
  return t('supervisor.break_ordinal', { ordinal })
}
