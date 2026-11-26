import type { SelectedLoadUncertainty, SimMcOut } from '../api/types'

/**
 * Owner decision 2026-11-26 (display only): a separate-lines "Insufficient evidence" decision gets pilot
 * guidance when the recorded Many variations run it cites passed in every row, and the recorded
 * selected-load family settled no check as failed but left some not enough to tell. Every input is a
 * stored value; nothing is recomputed. Missing or malformed values hide the guidance.
 */
export function showSelectedRawPassGuidance({ status, mcRows, loadUncertainty }: {
  status: string | null | undefined
  /** Rows of the Many variations job the decision cites (evidence_ids.mc); empty when that run is not available. */
  mcRows: readonly SimMcOut[]
  loadUncertainty: SelectedLoadUncertainty | null | undefined
}): boolean {
  if (status !== 'insufficient_evidence') return false
  if (mcRows.length === 0 || !mcRows.every((row) => row.status === 'PASS')) return false
  const fail = loadUncertainty?.fail_count
  const insufficient = loadUncertainty?.insufficient_count
  const count = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0
  return count(fail) && count(insufficient) && fail === 0 && insufficient > 0
}
