// Shared rules for Queue simulation evidence (moved from the former SimulationPage, unchanged).
import type {
  SelectedDecision,
  SelectedDesResult,
  SelectedMcResult,
  SelectedValidationResult,
  SimValidateOut,
} from '../api/types'

export const MC_MAX_TRIALS = 100000

export function parseSeed(raw: string): number | null {
  if (!raw.trim()) return null
  const value = Number(raw)
  return Number.isInteger(value) ? value : null
}

export function requestError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export function validProbability(value: number): boolean {
  return Number.isFinite(value) && value > 0 && value <= 1
}

export function validationPasses(row: SimValidateOut, cap: number): boolean {
  return (
    row.simulation_supported !== false
    && !row.validation_reason
    && !['ERROR', 'Critical', 'Unstable'].includes(row.sim_status)
    && Number.isFinite(row.mc_failure_rate)
    && row.mc_failure_rate <= cap
    && row.mc_failure_rate_adequate === true
  )
}

export function storedNumberDiffers(raw: string, stored: unknown): boolean {
  return typeof stored === 'number' && Number.isFinite(stored) && Number(raw) !== stored
}

export function storedSeedDiffers(raw: string, stored: unknown): boolean {
  if (stored === null) return parseSeed(raw) !== null
  return typeof stored === 'number' && Number.isFinite(stored) && parseSeed(raw) !== stored
}

export function isSelectedDesResult(value: unknown): value is SelectedDesResult {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return record.provenance === 'SELECTED' && Array.isArray(record.periods)
}

export function isSelectedMcResult(value: unknown): value is SelectedMcResult {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return record.provenance === 'SELECTED' && Array.isArray(record.results)
}

export function isSelectedValidationResult(value: unknown): value is SelectedValidationResult {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return record.provenance === 'SELECTED'
    && typeof record.verdict === 'object'
    && record.verdict !== null
    && Array.isArray(record.periods)
}

export function isSelectedDecision(value: unknown): value is SelectedDecision {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return record.provenance === 'SELECTED'
    && typeof record.status === 'string'
    && Array.isArray(record.rationale)
}

export function validationVerdictLabel(status: string | null, t: (key: string) => string): string {
  if (status === 'pass') return t('simulation.sep_validation_pass')
  if (status === 'fail') return t('simulation.sep_validation_fail')
  return t('simulation.sep_validation_insufficient')
}

export function decisionStatusLabel(status: string | null, t: (key: string) => string): string {
  if (status === 'adopt') return t('simulation.sep_decision_adopt')
  if (status === 'revise') return t('simulation.sep_decision_revise')
  if (status === 'insufficient_evidence') return t('simulation.sep_decision_insufficient')
  return t('simulation.sep_decision_conditional')
}
