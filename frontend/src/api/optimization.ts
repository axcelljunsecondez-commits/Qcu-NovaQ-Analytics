import planningDefaults from './planning-defaults.json'
import { http } from '../lib/http'
import type { SegmentInput, OptimizationOut } from './types'

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
