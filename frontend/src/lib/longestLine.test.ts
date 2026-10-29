import { describe, expect, it } from 'vitest'
import type { SelectedDesLaneRow, SelectedDesPeriod, SimDesOut } from '../api/types'
import { currentMatrix, laneOrder, planMatrix } from './longestLine'

function des(time: string, queue: string | null, maxQueue: number, extra: Partial<SimDesOut> = {}): SimDesOut {
  return { time, queue_id: queue, lambda: 2, mu: 3, c: 1, rho_sim: 0.5, Lq_sim: 0.2, Wq_sim: 0.05, max_queue: maxQueue, served: 10, dropped: 0,
    status: 'Normal', error: null, simulation_supported: true, ...extra }
}

function lane(queue: string, maxQueue: number | null, extra: Partial<SelectedDesLaneRow> = {}): SelectedDesLaneRow {
  return { time: 't', queue_id: queue, server_id: `server:${queue}`, lambda: 2, lambda_routed: 2, mu: 3, c: 1, arrivals: 4, served: 4, waiting: 0,
    in_service: 0, abandoned: null, Wq_sim: 0.05, rho_sim: 0.4, max_queue: maxQueue, active: true, simulation_supported: true, error: null,
    metric_provenance: 'simulated', customer_conservation: true, ...extra }
}

function period(time: string, results: SelectedDesLaneRow[], active: string[], inactive: string[]): SelectedDesPeriod {
  return { time, active_queue_ids: active, inactive_queue_ids: inactive, evaluation_status: 'FEASIBLE', conservation: true, total_lambda: 4,
    total_cost: null, server_cost: null, waiting_cost: null, results,
    trace: { trace: [], trace_hours: 1, total_hours: 1, event_count: 0, truncated: false, abandonment_supported: false, segments: [] } }
}

describe('lane order', () => {
  it('keeps the Setup order and appends lanes the run returned that the Setup does not list', () => {
    expect(laneOrder(['c1', 'c2'], ['c2', 'x9', 'c1'])).toEqual(['c1', 'c2', 'x9'])
  })
})

describe('Current run matrix', () => {
  it('is null for a run without lane rows (shared line)', () => {
    expect(currentMatrix([des('08:00-09:00', null, 4)], [])).toBeNull()
  })

  it('takes each row max over staffed cashiers only and marks a missing cashier as not staffed', () => {
    const matrix = currentMatrix([
      des('08:00-09:00', 'c1', 1), des('08:00-09:00', 'c2', 3),
      des('09:00-10:00', 'c2', 0),
    ], ['c1', 'c2'])!
    expect(matrix.lanes).toEqual(['c1', 'c2'])
    expect(matrix.rows.map((row) => row.time)).toEqual(['08:00-09:00', '09:00-10:00'])
    expect(matrix.rows[0].max).toBe(3)
    expect(matrix.rows[1].cells[0]).toEqual({ lane: 'c1', staffed: false, value: null, rho: null })
    expect(matrix.rows[1].cells[1]).toMatchObject({ staffed: true, value: 0 })
    // A staffed zero is a value, not a gap.
    expect(matrix.rows[1].max).toBe(0)
    expect(matrix.dayMax).toBe(3)
    expect(matrix.peaks).toEqual([{ time: '08:00-09:00', lane: 'c2' }])
  })

  it('gives a period that could not be simulated no value', () => {
    const matrix = currentMatrix([des('08:00-09:00', 'c1', 0, { error: 'Unsupported', simulation_supported: false })], ['c1'])!
    expect(matrix.rows[0].cells[0]).toEqual({ lane: 'c1', staffed: true, value: null, rho: null })
    expect(matrix.rows[0].max).toBeNull()
    expect(matrix.dayMax).toBeNull()
    expect(matrix.peaks).toEqual([])
  })

  it('lists every cell that holds the largest value', () => {
    const matrix = currentMatrix([des('a', 'c1', 2), des('a', 'c2', 2), des('b', 'c1', 2)], ['c1', 'c2'])!
    expect(matrix.peaks).toEqual([{ time: 'a', lane: 'c1' }, { time: 'a', lane: 'c2' }, { time: 'b', lane: 'c1' }])
  })
})

describe('Suggested plan matrix', () => {
  it('uses the plan rows, hides inactive lanes as not staffed and keeps a null max_queue null', () => {
    const matrix = planMatrix([
      period('08:00', [lane('c1', 4), lane('c2', 9, { active: false })], ['c1'], ['c2']),
      period('09:00', [lane('c1', null), lane('c2', 1)], ['c1', 'c2'], []),
    ], ['c1', 'c2'])!
    expect(matrix.rows[0].cells[1]).toEqual({ lane: 'c2', staffed: false, value: null, rho: null })
    // The inactive lane's stored 9 is never the row maximum.
    expect(matrix.rows[0].max).toBe(4)
    expect(matrix.rows[1].cells[0]).toMatchObject({ staffed: true, value: null })
    expect(matrix.rows[1].max).toBe(1)
    expect(matrix.dayMax).toBe(4)
    expect(matrix.peaks).toEqual([{ time: '08:00', lane: 'c1' }])
  })

  it('treats a lane listed in inactive_queue_ids as not staffed even if its row says active', () => {
    const matrix = planMatrix([period('08:00', [lane('c1', 2), lane('c2', 5)], ['c1'], ['c2'])], ['c1', 'c2'])!
    expect(matrix.rows[0].cells[1].staffed).toBe(false)
    expect(matrix.rows[0].max).toBe(2)
  })

  it('shows a staffed lane without a row as Unavailable, and an unlisted lane as not staffed', () => {
    const matrix = planMatrix([period('08:00', [lane('c1', 2)], ['c1', 'c2'], [])], ['c1', 'c2', 'c3'])!
    expect(matrix.rows[0].cells.map((cell) => [cell.staffed, cell.value])).toEqual([[true, 2], [true, null], [false, null]])
  })

  it('is null when the plan has no lane rows', () => {
    expect(planMatrix([period('08:00', [], [], [])], ['c1'])).toBeNull()
  })
})
