export const RADAR_THETA = ['Cost\nEfficiency', 'Wait\nTime', 'Utilization', 'Server\nEfficiency']

export interface RadarRow {
  cost_current: number | null
  cost_optimal: number | null
  Wq_current: number | null
  Wq_optimal: number | null
  rho_current: number | null
  rho_optimal: number | null
  c_current: number
  c_optimal: number | null
  lambda?: number | null
}

export const DEFAULT_TARGET_UTILIZATION = 0.7

function sum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((acc, v) => acc + (v ?? 0), 0)
}

function mean(values: Array<number | null | undefined>): number {
  const present = values.filter((v): v is number => v !== null && v !== undefined && !Number.isNaN(v))
  if (present.length === 0) return 0
  return present.reduce((acc, v) => acc + v, 0) / present.length
}

function weightedMean(
  values: Array<number | null | undefined>,
  weights: Array<number | null | undefined>,
): number | null {
  let numerator = 0
  let denominator = 0
  values.forEach((v, i) => {
    const w = weights[i]
    if (v !== null && v !== undefined && !Number.isNaN(v) && w !== null && w !== undefined && Number.isFinite(w) && w > 0) {
      numerator += v * w
      denominator += w
    }
  })
  return denominator > 0 ? numerator / denominator : null
}

function clamp(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100) / 100))
}

export function computeRadarScores(
  rows: RadarRow[],
  { current, targetRho = DEFAULT_TARGET_UTILIZATION }: { current: boolean; targetRho?: number },
): { r: number[]; theta: string[] } {
  const totalCostCurrent = sum(rows.map((r) => r.cost_current))
  const totalCostOptimized = sum(rows.map((r) => r.cost_optimal))
  const costBest = Math.min(totalCostCurrent, totalCostOptimized)

  const lambdas = rows.map((r) => r.lambda)
  const wqCurrent = weightedMean(rows.map((r) => r.Wq_current), lambdas)
  const wqOptimized = weightedMean(rows.map((r) => r.Wq_optimal), lambdas)
  const wqBest = Math.min(wqCurrent ?? 0, wqOptimized ?? 0)

  const rhoCurrent = mean(rows.map((r) => r.rho_current))
  const rhoOptimized = mean(rows.map((r) => r.rho_optimal))

  const serversCurrent = sum(rows.map((r) => r.c_current))
  const serversOptimized = sum(rows.map((r) => r.c_optimal))
  const serversBest = Math.min(serversCurrent, serversOptimized)

  const ratioScore = (trace: number, best: number) => clamp(trace > 0 ? (100 * best) / trace : 100)
  const waitScore = (wq: number | null) => (wq === null ? 50 : ratioScore(wq, wqBest))
  const utilScore = (rho: number) => clamp(Math.max(0, 100 * (1 - Math.abs(targetRho - rho))))

  const r = current
    ? [
        ratioScore(totalCostCurrent, costBest),
        waitScore(wqCurrent),
        utilScore(rhoCurrent),
        ratioScore(serversCurrent, serversBest),
      ]
    : [
        ratioScore(totalCostOptimized, costBest),
        waitScore(wqOptimized),
        utilScore(rhoOptimized),
        ratioScore(serversOptimized, serversBest),
      ]
  return { r, theta: RADAR_THETA }
}