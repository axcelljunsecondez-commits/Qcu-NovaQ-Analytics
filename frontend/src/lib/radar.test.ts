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
    lambda: 30,
  },
]

const THETA = ['Cost\nEfficiency', 'Wait\nTime', 'Utilization', 'Server\nEfficiency']

describe('computeRadarScores', () => {
  it('computes exact parity scores for the current plan at the default target', () => {
    expect(computeRadarScores(rows, { current: true })).toEqual({
      r: [62.5, 50, 80, 80],
      theta: THETA,
    })
  })

  it('computes exact parity scores for the optimized plan at the default target', () => {
    expect(computeRadarScores(rows, { current: false })).toEqual({
      r: [100, 100, 100, 100],
      theta: THETA,
    })
  })

  it('scores utilization against the given target utilization', () => {
    const at85 = computeRadarScores(rows, { current: true, targetRho: 0.85 })
    const at70 = computeRadarScores(rows, { current: true, targetRho: 0.7 })
    expect(at85.r[2]).toBe(95)
    expect(at70.r[2]).toBe(80)
  })

  it('weights wait time by arrival rate', () => {
    const weighted: RadarRow[] = [
      {
        cost_current: 100,
        cost_optimal: 100,
        Wq_current: 0.5,
        Wq_optimal: 0.5,
        rho_current: 0.7,
        rho_optimal: 0.7,
        c_current: 1,
        c_optimal: 1,
        lambda: 10,
      },
      {
        cost_current: 100,
        cost_optimal: 100,
        Wq_current: 0.1,
        Wq_optimal: 0.5,
        rho_current: 0.7,
        rho_optimal: 0.7,
        c_current: 1,
        c_optimal: 1,
        lambda: 90,
      },
    ]
    const current = computeRadarScores(weighted, { current: true })
    const optimized = computeRadarScores(weighted, { current: false })
    const weightedCurrentWq = (0.5 * 10 + 0.1 * 90) / 100
    const weightedOptWq = (0.5 * 10 + 0.5 * 90) / 100
    const wqBest = Math.min(weightedCurrentWq, weightedOptWq)
    expect(current.r[1]).toBeCloseTo(100 * wqBest / weightedCurrentWq, 2)
    expect(optimized.r[1]).toBeCloseTo(100 * wqBest / weightedOptWq, 2)
  })

  it('scores the wait axis as neutral when no wait data exists', () => {
    const noData: RadarRow[] = [
      {
        cost_current: 100,
        cost_optimal: 50,
        Wq_current: null,
        Wq_optimal: null,
        rho_current: 0.7,
        rho_optimal: 0.7,
        c_current: 2,
        c_optimal: 1,
        lambda: 10,
      },
    ]
    const current = computeRadarScores(noData, { current: true })
    const optimized = computeRadarScores(noData, { current: false })
    expect(current.r[1]).toBe(50)
    expect(optimized.r[1]).toBe(50)
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
    expect(r[1]).toBe(50)
  })

  it('scores the worse trace as non-zero and proportional when current is strictly worse', () => {
    const worse = computeRadarScores(rows, { current: true })
    const better = computeRadarScores(rows, { current: false })
    expect(worse.r[0]).toBeGreaterThan(0)
    expect(worse.r[1]).toBeGreaterThan(0)
    expect(worse.r[3]).toBeGreaterThan(0)
    expect(worse.r[0]).toBeLessThan(better.r[0])
    expect(worse.r[1]).toBeLessThan(better.r[1])
    expect(worse.r[3]).toBeLessThan(better.r[3])
    expect(worse.r[2]).toBeGreaterThan(0)
    expect(better.r[2]).toBeGreaterThan(0)
  })
})