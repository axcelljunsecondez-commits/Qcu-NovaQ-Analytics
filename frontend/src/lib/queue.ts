/**
 * Shared queue-related utilities for NovaQ frontend.
 */
import type { DatasetOut, SegmentRow } from '../api/types'

/**
 * Extract segment rows from a dataset's normalized data.
 * Handles optional fields (variance, K, theta, server_cost) with proper validation.
 */
export function segmentsOf(dataset: DatasetOut): SegmentRow[] {
  return (dataset.normalized ?? []).map((row) => {
    const variance = typeof row.variance === 'number' && Number.isFinite(row.variance) ? row.variance : undefined
    const K = typeof row.K === 'number' && Number.isInteger(row.K) && row.K >= 1 ? row.K : undefined
    const theta = typeof row.theta === 'number' && Number.isFinite(row.theta) ? row.theta : undefined
    const serverCost = typeof row.server_cost === 'number' && Number.isFinite(row.server_cost) ? row.server_cost : undefined
    return {
      time: String(row.time),
      lambda: Number(row.lambda),
      mu: Number(row.mu),
      c: Number(row.c),
      ...(variance !== undefined ? { variance } : {}),
      ...(K !== undefined ? { K } : {}),
      ...(theta !== undefined && theta >= 0 ? { theta } : {}),
      ...(serverCost !== undefined ? { server_cost: serverCost } : {}),
    }
  })
}

/**
 * Check if a rate input is numeric and finite.
 */
export function isValidRate(value: unknown): boolean {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * Safely convert a value to a finite number, returning 0 for invalid values.
 */
export function safeNumber(value: number | null | undefined, fallback = 0): number {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return fallback
  }
  return Number.isFinite(value) ? value : fallback
}
