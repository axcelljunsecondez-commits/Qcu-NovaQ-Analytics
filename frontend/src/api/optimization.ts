import planningDefaults from './planning-defaults.json'
import { http } from '../lib/http'
import type { AnalysisProjectOut, SegmentInput, OptimizationOut, SeparateSchedule } from './types'

export interface OptimizeOptions {
  target_utilization?: number
  server_cost_per_hr?: number
  customer_waiting_cost?: number
  min_servers?: number
  max_wait_minutes?: number | null
  max_servers?: number
  cost_per_abandonment?: number
  abandonment_rate?: number
}

export const DEFAULT_OPTIONS: OptimizeOptions = planningDefaults

export interface OptimizeBatchResponse {
  results: OptimizationOut[]
}

export async function optimizeBatch(
  segments: SegmentInput[],
  options: OptimizeOptions = {},
): Promise<OptimizeBatchResponse> {
  const { data } = await http.post<OptimizeBatchResponse>('/optimize/batch', {
    segments,
    ...options,
  })
  return data
}

export interface SeparateOptimizeOptions {
  target_utilization?: number
  server_cost_per_hr?: number
  customer_waiting_cost?: number
  lambda_multiplier?: number
  min_active_lanes?: number | null
  max_active_lanes?: number | null
  des?: {
    replications?: number
    base_seed?: number
    duration_hours?: number
    max_events?: number
  }
}

export async function optimizeSeparate(
  analysisId: number,
  datasetId: number,
  options: SeparateOptimizeOptions = {},
): Promise<{ schedule: SeparateSchedule }> {
  const { data } = await http.post<{ schedule: SeparateSchedule }>(
    `/analyses/${analysisId}/workflow/optimize/separate`,
    { dataset_id: datasetId, ...options },
  )
  return data
}

export interface BreakOptimizeOptions {
  dataset_id?: number | null
  target_rho?: number
  max_shift_minutes?: number
  des?: { replications?: number; base_seed?: number }
}

export interface BreakEntry {
  queue_id: string
  label: string
  scheduled_start_time: string
  duration_minutes: number
}

export interface ProposedBreakEntry extends BreakEntry {
  current_start_time: string
  shift_minutes: number
}

export interface BreakSlot {
  start: string
  end: string
  lambda: number
  mu: number
  working_before: number
  working_after: number
  rho_before: number | null
  rho_after: number | null
}

export interface BreakDesSummary {
  mean_wait_minutes: number | null
  max_queue: number | null
  admitted: number | null
  served: number | null
  customer_conservation: boolean
}

export interface BreakDesSchedule {
  summary: BreakDesSummary
  replications: Array<Omit<BreakDesSummary, 'max_queue'> & { seed: number; max_queue: number }>
  periods: Array<{ time: string; mean_wait_minutes: number | null }>
}

/** 95% interval of the paired per-replication wait change (proposed − current), minutes. */
export interface PairedWaitChange {
  mean: number | null
  sd: number | null
  se: number | null
  ci_lower: number | null
  ci_upper: number | null
  n: number
  verdict: 'shorter' | 'longer' | 'no_clear_difference'
}

export interface BreakOptimizeResult {
  status: 'improved' | 'no_improvement'
  target_rho: number
  max_shift_minutes: number
  all_below_target: boolean
  current_breaks: BreakEntry[]
  proposed_breaks: ProposedBreakEntry[]
  moves: Array<{ queue_id: string; label: string; from: string; to: string; duration_minutes: number }>
  slots: BreakSlot[]
  peak_rho: { before: number | null; after: number | null }
  slots_above_target: { before: number; after: number }
  staffing_gaps: Array<{ start: string; end: string; on_shift: number; rho_no_breaks: number | null }>
  des: {
    seeds: number[]
    current: BreakDesSchedule
    proposed: BreakDesSchedule
    comparison: {
      mean_wait_change_minutes: number | null
      proposed_better_runs: number
      runs: number
      paired_wait_change?: PairedWaitChange
    }
  }
  notes: string[]
  /** Fingerprint of the Setup the proposal used; Apply is refused if it changed. */
  setup_hash: string
  /** Dataset the proposal used; Apply is refused unless it is still the latest valid one. */
  dataset_id: number
}

export async function optimizeSeparateBreaks(
  analysisId: number,
  options: BreakOptimizeOptions = {},
): Promise<BreakOptimizeResult> {
  const { data } = await http.post<BreakOptimizeResult>(
    `/analyses/${analysisId}/workflow/optimize/separate/breaks`,
    options,
  )
  return data
}

export interface BreakApplyRequest {
  target_rho: number
  max_shift_minutes: number
  setup_hash: string
  dataset_id: number
}

/** The server re-runs placement and writes only the break start times into Setup. */
export async function applySeparateBreaks(
  analysisId: number,
  body: BreakApplyRequest,
): Promise<{ analysis: AnalysisProjectOut; moves_applied: number }> {
  const { data } = await http.post<{ analysis: AnalysisProjectOut; moves_applied: number }>(
    `/analyses/${analysisId}/workflow/optimize/separate/breaks/apply`,
    body,
  )
  return data
}
