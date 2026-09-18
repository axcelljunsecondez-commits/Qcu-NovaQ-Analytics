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
