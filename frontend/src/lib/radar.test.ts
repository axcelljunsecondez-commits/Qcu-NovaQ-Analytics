import { describe, it, expect } from 'vitest'
import { computeRadarScores, type RadarRow } from './radar'

const rows: RadarRow[] = [
  {
    cost_current: 800,
    cost_optimal: 500,
    Wq_current: 0.1,
    Wq_optimal: 0.05,
    rho_current: 0.9,
    rho_optimal: 0.7,
    c_current: 10,
    c_optimal: 8,
    mc_failure_rate: 0.2,
  },
]

const THETA = ['Cost\nEfficiency', 'Wait\nTime', 'Utilization', 'Stability', 'Server\nEfficiency']

describe('computeRadarScores', () => {
  it('computes exact legacy parity scores for the current plan', () => {
    expect(computeRadarScores(rows, { current: true })).toEqual({
      r: [0, 0, 95, 80, 0],
      theta: THETA,
    })
  })

  it('computes exact legacy parity scores for the optimized plan', () => {
    expect(computeRadarScores(rows, { current: false })).toEqual({
      r: [37.5, 50, 85, 88, 20],
      theta: THETA,
    })
  })

  it('clamps scores to 0-100 and tolerates null fields without NaN', () => {
    const bad: RadarRow[] = [
      {
        cost_current: null,
        cost_optimal: null,
        Wq_current: null,
        Wq_optimal: null,
        rho_current: 2.5,
        rho_optimal: 0.85,
        c_current: 0,
        c_optimal: 0,
      },
    ]
    const { r } = computeRadarScores(bad, { current: true })
    expect(r.every((v) => v >= 0 && v <= 100)).toBe(true)
    expect(r.every((v) => !Number.isNaN(v))).toBe(true)
    expect(r[2]).toBe(0)
    expect(r[0]).toBe(100)
  })
})
