import { describe, expect, it } from 'vitest'
import { segmentsOf } from './queue'
import type { DatasetOut } from '../api/types'

function dataset(normalized: Record<string, unknown>[]): DatasetOut {
  return {
    id: 1,
    analysis_id: 7,
    name: 'd',
    source_filename: 'd.csv',
    source_format: 'csv',
    row_count: normalized.length,
    validation: { ok: true, message: 'ok' },
    created_at: '2026-09-16T00:00:00Z',
    normalized,
  }
}

describe('segmentsOf queue identity', () => {
  it('preserves separate-queue structure and model identity for the optimizer gate', () => {
    const rows = segmentsOf(dataset([
      { time: '08:00', queue_id: 'queue_1', queue_structure: 'separate_queues', model_id: 'parallel_mg1', lambda: 5, mu: 4, c: 1, variance: 0.0025 },
    ]))
    expect(rows).toHaveLength(1)
    expect(rows[0].queue_structure).toBe('separate_queues')
    expect(rows[0].model_id).toBe('parallel_mg1')
  })

  it('omits identity fields when the dataset does not carry them', () => {
    const rows = segmentsOf(dataset([
      { time: '08:00', lambda: 30, mu: 12, c: 3 },
    ]))
    expect(rows[0]).not.toHaveProperty('queue_structure')
    expect(rows[0]).not.toHaveProperty('model_id')
  })
})
