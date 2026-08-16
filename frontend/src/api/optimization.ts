import { http } from '../lib/http'
import type { SegmentInput, OptimizationOut } from './types'

export interface OptimizeOptions {
  target_utilization?: number
  server_cost_per_hr?: number
  customer_waiting_cost?: number
  max_servers?: number
  cost_per_abandonment?: number
  abandonment_rate?: number
}

export const DEFAULT_OPTIONS: OptimizeOptions = {
  target_utilization: 0.7,
  server_cost_per_hr: 87,
  customer_waiting_cost: 100,
  max_servers: 24,
  cost_per_abandonment: 60,
  abandonment_rate: 0.1,
}

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
