import type { OptimizationOut } from '../api/types'

function finiteNonNegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

/** Operational fields needed to show the saved baseline and recommendation. */
export function operationalComparisonComplete(rows: OptimizationOut[]): boolean {
  return rows.length > 0 && rows.every((row) =>
    Number.isInteger(row.c_current) && row.c_current > 0 &&
    finiteNonNegative(row.rho_current) &&
    row.optimized_stable === true &&
    row.c_optimal !== null && Number.isInteger(row.c_optimal) && row.c_optimal > 0 &&
    finiteNonNegative(row.rho_optimal) &&
    finiteNonNegative(row.Wq_optimal) &&
    finiteNonNegative(row.Lq_optimal))
}

export function comparisonComplete(rows: OptimizationOut[]): boolean {
  return operationalComparisonComplete(rows) && rows.every((row) => row.current_stable &&
    [row.cost_current, row.cost_optimal].every(finiteNonNegative))
}

export function comparisonTotals(rows: OptimizationOut[]) {
  if (!comparisonComplete(rows)) return null
  const current = rows.reduce((sum, row) => sum + row.cost_current!, 0)
  const optimal = rows.reduce((sum, row) => sum + row.cost_optimal!, 0)
  return { current, optimal, savings: current - optimal }
}
