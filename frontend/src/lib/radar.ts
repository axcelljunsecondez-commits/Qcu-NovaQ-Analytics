export const RADAR_THETA = ['Cost\nEfficiency', 'Wait\nTime', 'Utilization', 'Server\nEfficiency']

export interface RadarRow {
  cost_current: number | null
  cost_optimal: number | null
  Wq_current: number | null
  Wq_optimal: number | null
  rho_current: number | null
  rho_optimal: number | null
  c_current: number
  c_optimal: number
  mc_failure_rate?: number | null
}

function sum(values: Array<number | null>): number {
  return values.reduce<number>((acc, v) => acc + (v ?? 0), 0)
}

function mean(values: Array<number | null | undefined>): number {
  const present = values.filter((v): v is number => v !== null && v !== undefined && !Number.isNaN(v))
  if (present.length === 0) return 0
  return present.reduce((acc, v) => acc + v, 0) / present.length
}

function clamp(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100) / 100))
}

export function computeRadarScores(
  rows: RadarRow[],
  { current }: { current: boolean },
): { r: number[]; theta: string[] } {
  const totalCostCurrent = sum(rows.map((r) => r.cost_current))
  const totalCostOptimized = sum(rows.map((r) => r.cost_optimal))
  const costMax = Math.max(totalCostCurrent, totalCostOptimized) || 1

  const wqCurrent = mean(rows.map((r) => r.Wq_current))
  const wqOptimized = mean(rows.map((r) => r.Wq_optimal))
  const wqMax = Math.max(wqCurrent, wqOptimized) || 1

  const rhoCurrent = mean(rows.map((r) => r.rho_current))
  const rhoOptimized = mean(rows.map((r) => r.rho_optimal))

  const serversCurrent = sum(rows.map((r) => r.c_current))
  const serversOptimized = sum(rows.map((r) => r.c_optimal))
  const serversMax = Math.max(serversCurrent, serversOptimized) || 1

  const r = current
    ? [
        clamp(100 * (1 - totalCostCurrent / costMax)),
        clamp(100 * (1 - wqCurrent / wqMax)),
        clamp(Math.max(0, 100 * (1 - Math.abs(0.85 - rhoCurrent)))),
        clamp(100 * (1 - serversCurrent / serversMax)),
      ]
    : [
        clamp(100 * (1 - totalCostOptimized / costMax)),
        clamp(100 * (1 - wqOptimized / wqMax)),
        clamp(Math.max(0, 100 * (1 - Math.abs(0.85 - rhoOptimized)))),
        clamp(100 * (1 - serversOptimized / serversMax)),
      ]
  return { r, theta: RADAR_THETA }
}
