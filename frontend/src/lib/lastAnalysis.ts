import type { AnalysisProjectOut } from '../api/types'
import { readStorage, writeStorage } from './safeStorage'

export const LAST_ANALYSIS_KEY = 'novaq_last_analysis'

const listeners = new Set<() => void>()

export function storedLastAnalysis(): string | null {
  return readStorage(LAST_ANALYSIS_KEY)
}

export function subscribeLastAnalysis(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function rememberLastAnalysis(id: number): void {
  if (!Number.isInteger(id) || id <= 0 || storedLastAnalysis() === String(id)) return
  writeStorage(LAST_ANALYSIS_KEY, String(id))
  listeners.forEach((listener) => listener())
}

// The stored id is only a hint: it is used only while it still names an
// unarchived analysis returned by GET /analyses for the signed-in user.
export function resolveLastAnalysis(analyses: AnalysisProjectOut[] | undefined, stored = storedLastAnalysis()): number | null {
  const id = Number(stored)
  if (!analyses || !Number.isInteger(id) || id <= 0) return null
  return analyses.some((item) => item.id === id && !item.archived_at) ? id : null
}
