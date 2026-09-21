import { describe, expect, it } from 'vitest'
import { generateOptimizationInsights } from './insights'

const t = (key: string, params?: Record<string, string | number>) =>
  params ? `${key} ${JSON.stringify(params)}` : key

function titles(current: number | null, optimized: number | null) {
  return generateOptimizationInsights(current, optimized, null, null, null, t)
    .map((insight) => insight.title)
}

describe('generateOptimizationInsights null-vs-zero semantics', () => {
  it('compares two valid staffing endpoints', () => {
    expect(titles(4, 2)).toContain('insights.staffing_reduction_title')
    expect(titles(2, 4)).toContain('insights.staffing_increase_title')
    expect(titles(3, 3)).toHaveLength(0)
  })

  it('preserves a genuine numeric zero endpoint', () => {
    const reduction = generateOptimizationInsights(2, 0, null, null, null, t)
    expect(reduction.map((i) => i.title)).toContain('insights.staffing_reduction_title')
    expect(reduction[0].message).toContain('"recommended":0')
    // Equal zeroes compare as equal: no fabrication, no crash.
    expect(titles(0, 0)).toHaveLength(0)
  })

  it('emits no staffing comparison when either endpoint is unavailable', () => {
    expect(titles(3, null)).toHaveLength(0)
    expect(titles(null, 4)).toHaveLength(0)
    expect(titles(null, null)).toHaveLength(0)
  })

  it('still reports wait improvement and high utilization for valid numbers', () => {
    const insights = generateOptimizationInsights(3, 4, 10, 5, 0.95, t)
    const mapped = insights.map((i) => i.title)
    expect(mapped).toContain('insights.staffing_increase_title')
    expect(mapped).toContain('insights.wait_improvement_title')
    expect(mapped).toContain('insights.high_utilization_title')
  })

  it('warns on high utilization from the same 90% line as the Critical badge', () => {
    const warning = (rho: number) => generateOptimizationInsights(null, null, null, null, rho, t)
      .find((i) => i.title === 'insights.high_utilization_title')
    expect(warning(0.9)).toBeDefined()
    expect(warning(0.99 / 1.1)).toBeDefined() // exact 0.9 that computes as 0.8999999999999999
    expect(warning(0.8999)).toBeUndefined()
  })

  it('does not divide by a zero wait or warn on missing inputs', () => {
    expect(generateOptimizationInsights(3, 4, 0, 0, null, t)
      .map((i) => i.title)).not.toContain('insights.wait_improvement_title')
    expect(generateOptimizationInsights(3, 4, null, 5, null, t)
      .map((i) => i.title)).not.toContain('insights.wait_improvement_title')
    expect(generateOptimizationInsights(3, 4, 10, 5, 0, t)
      .map((i) => i.title)).not.toContain('insights.high_utilization_title')
  })
})
