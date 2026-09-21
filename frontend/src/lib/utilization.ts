/**
 * Utilization status bands, mirroring backend/queueing_engine/utilization.py:
 * Lean < 60% ≤ Normal ≤ 80% < Peak < 90% ≤ Critical ≤ 100% < Unstable.
 */
export type UtilizationBand = 'Lean' | 'Normal' | 'Peak' | 'Critical' | 'Unstable'

/**
 * λ / (cμ) carries float noise: an exact ρ of 0.9 can arrive as
 * 0.8999999999999999. A value this close to a boundary counts as on it.
 */
export const THRESHOLD_TOLERANCE = 1e-9

export function utilizationBand(rho: number): UtilizationBand {
  if (rho > 1 + THRESHOLD_TOLERANCE) return 'Unstable'
  if (rho >= 0.9 - THRESHOLD_TOLERANCE) return 'Critical'
  if (rho > 0.8 + THRESHOLD_TOLERANCE) return 'Peak'
  if (rho >= 0.6 - THRESHOLD_TOLERANCE) return 'Normal'
  return 'Lean'
}
