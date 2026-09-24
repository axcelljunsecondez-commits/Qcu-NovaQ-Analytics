/**
 * One separate-queue schedule used by the Optimize, Compare and Reports tests (D5).
 *
 * Optimize shows each period's hourly cost rate and its whole-period cost. The backend
 * builds Compare's per-period cost and plan total, and the report's selected total, from
 * the same `optimum.period_costs` (backend/api/workflow.py separate_comparison and
 * backend/reports/separate_report.py), so the derived values below are read from the
 * schedule rather than typed in.
 */

export const HOURLY_RATE = 120.4

export function periodCostPeriod(time: string, minutes: number) {
  const hours = minutes / 60
  return {
    time,
    overall: 'OPTIMAL',
    reason: null,
    duration_hours: hours,
    current_active_lanes: ['lane-a', 'lane-b'],
    optimal_active_lanes: 2,
    adjustment: 0,
    evaluation_method: 'DES_REPLICATIONS',
    replication_seeds: [42, 43, 44, 45, 46],
    optimum: {
      active_lane_count: 2,
      recommendation: 'KEEP',
      total_cost: HOURLY_RATE,
      candidate_utilization: 0.6,
      estimated_optimal: true,
      cost_uncertainty: { mean: HOURLY_RATE, sd: 4, se: 1.8, ci_lower: 115.4, ci_upper: 125.4, n: 5 },
      period_costs: {
        duration_hours: hours,
        staffing: { mean: 174 * hours, sd: 0, se: 0, ci_lower: 174 * hours, ci_upper: 174 * hours, n: 5 },
        waiting: null,
        total: { mean: HOURLY_RATE * hours, sd: 4 * hours, se: 1.8 * hours,
                 ci_lower: 115.4 * hours, ci_upper: 125.4 * hours, n: 5 },
        unavailable_reason: null,
      },
    },
    candidates: [],
  }
}

export const periodCostSchedule = {
  overall: 'COMPLETE',
  reason: null,
  target_utilization: 0.7,
  evaluation_method: 'DES_REPLICATIONS',
  des: { replications: 5, base_seed: 42, duration_hours: 24, max_events: 10000 },
  periods: [periodCostPeriod('08:00-09:00', 60), periodCostPeriod('09:00-09:30', 30)],
}

/** What the Compare endpoint returns per period and in total for this schedule. */
export const periodCostComparison = {
  periods: periodCostSchedule.periods.map((p) => ({
    time: p.time,
    duration_hours: p.duration_hours,
    current_active_lanes: p.current_active_lanes,
    optimal_active_lanes: p.optimal_active_lanes,
    adjustment: p.adjustment,
    peak_util: p.optimum.candidate_utilization,
    wait_mean: 0.05,
    wait_ci: null,
    waiting_cost_mean: null,
    total_cost_mean: p.optimum.period_costs.total.mean,
    total_cost_ci: [p.optimum.period_costs.total.ci_lower, p.optimum.period_costs.total.ci_upper],
    status: 'OPTIMAL',
  })),
  total_cost_mean: periodCostSchedule.periods.reduce((sum, p) => sum + p.optimum.period_costs.total.mean, 0),
}

/** The report's selected total for this schedule: the sum of the period costs. */
export const periodCostReportTotal = periodCostComparison.total_cost_mean
