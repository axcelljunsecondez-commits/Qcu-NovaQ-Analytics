import planningDefaults from './planning-defaults.json'
import { http } from '../lib/http'
import type { SegmentInput, OptimizationOut, SeparateSchedule } from './types'

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
    comparison: { mean_wait_change_minutes: number | null; proposed_better_runs: number; runs: number }
  }
  notes: string[]
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
