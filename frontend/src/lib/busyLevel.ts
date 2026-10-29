// Busy Level rows for Analysis Results tab 2 (spec 2026-10-29 §5.3). Selection and labelling only:
// levels come from `utilizationBand` (its 1e-9 tolerance) on workloads the server returned.
import type { OptimizationOut, SeparateComparison, SeparatePlanComparison } from '../api/types'
import { busyLevel, dayStrip, finiteNumber, lineOf, timeOf, type ResultRow } from './results'
import { utilizationBand, type UtilizationBand } from './utilization'

export const LEVEL_ORDER: UtilizationBand[] = ['Lean', 'Normal', 'Peak', 'Critical', 'Unstable']

export interface LevelCell {
  time: string
  level: UtilizationBand | null
  rho: number | null
}

/** The plan's level: the server's unstable flag first, then the band of the workload (as the plan table did). */
export function planBand(rho: number | null, stable: boolean | null): UtilizationBand | null {
  if (stable === false) return 'Unstable'
  return rho === null ? null : utilizationBand(rho)
}

/** Current: one cell per period; separate lines take their busiest line (`dayStrip`). */
export function todayCells(rows: ResultRow[]): LevelCell[] {
  return dayStrip(rows).map((period) => ({ time: period.time, level: period.level, rho: period.rho }))
}

/** Separate lines, Suggested plan: the busiest cashier's simulated mean workload (`peak_util`). */
export function separatePlanCells(comparison: SeparateComparison, plan: SeparatePlanComparison): LevelCell[] {
  return comparison.current.periods.map((period) => {
    const rho = finiteNumber(plan.periods.find((item) => item.time === period.time)?.peak_util)
    return { time: period.time, level: planBand(rho, null), rho }
  })
}

/** Shared line, Suggested plan: the calculated workload with the plan's stability flag. */
export function sharedPlanCells(rows: OptimizationOut[]): LevelCell[] {
  return rows.map((row) => {
    const rho = finiteNumber(row.rho_optimal)
    return { time: row.time, level: planBand(rho, row.optimized_stable), rho }
  })
}

/** Levels present in the cells, in NovaQ's order; `unknown` when a cell has no level. */
export function presentLevels(cells: LevelCell[]): { levels: UtilizationBand[]; unknown: boolean } {
  const seen = new Set(cells.map((cell) => cell.level))
  return { levels: LEVEL_ORDER.filter((level) => seen.has(level)), unknown: seen.has(null) }
}

/** Index of the highest workload (first on a tie); null when none is known. */
export function peakCell(cells: LevelCell[]): number | null {
  let best: number | null = null
  cells.forEach((cell, index) => {
    if (cell.rho !== null && (best === null || cell.rho > (cells[best].rho as number))) best = index
  })
  return best
}

/** A takeaway may say "every hour is …" only when every cell has a level and a workload. */
export function complete(cells: LevelCell[]): boolean {
  return cells.length > 0 && cells.every((cell) => cell.level !== null && cell.rho !== null)
}

/** "Lean, Normal or Peak" from the translated level words and the connector word. */
export function joinLevels(words: string[], or: string): string {
  if (words.length <= 1) return words[0] ?? ''
  return `${words.slice(0, -1).join(', ')} ${or} ${words[words.length - 1]}`
}

export type PlanTakeaway =
  | { kind: 'below' }
  | { kind: 'above'; count: number }
  | null

/**
 * Separate plan takeaway: "below the plan's target" only when every period is below it;
 * otherwise the count strictly above it (as `periodWarnings`); none when a period sits exactly on it.
 */
export function separatePlanTakeaway(cells: LevelCell[], target: number | null): PlanTakeaway {
  if (target === null || !complete(cells)) return null
  const rhos = cells.map((cell) => cell.rho as number)
  if (rhos.every((rho) => rho < target)) return { kind: 'below' }
  const count = rhos.filter((rho) => rho > target).length
  return count > 0 ? { kind: 'above', count } : null
}

export interface LaneDetail {
  lane: string
  rho: number | null
  level: UtilizationBand | null
}

/** Separate lines, Current: each cashier line's workload in the chosen period, from the /current rows. */
export function laneDetail(rows: ResultRow[], time: string): LaneDetail[] {
  return rows.filter((row) => timeOf(row) === time && lineOf(row) !== null)
    .map((row) => ({ lane: lineOf(row) as string, rho: finiteNumber(row.rho), level: busyLevel(row) }))
}

export interface GroupDetail {
  counters: number | null
  rho: number | null
  level: UtilizationBand | null
}

/** Shared line, Current: the counter group of the chosen period, from the /current row. */
export function currentGroupDetail(rows: ResultRow[], time: string): GroupDetail | null {
  const row = rows.find((item) => timeOf(item) === time)
  return row ? { counters: finiteNumber(row.c), rho: finiteNumber(row.rho), level: busyLevel(row) } : null
}

/** Shared line, Suggested plan: the plan's counter group of the chosen period. */
export function planGroupDetail(rows: OptimizationOut[], time: string): GroupDetail | null {
  const row = rows.find((item) => item.time === time)
  if (!row) return null
  const rho = finiteNumber(row.rho_optimal)
  return { counters: finiteNumber(row.c_optimal), rho, level: planBand(rho, row.optimized_stable) }
}
