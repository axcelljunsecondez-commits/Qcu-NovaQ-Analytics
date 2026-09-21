export interface WorkloadEntry {
  queueId: unknown
  /** Finite ρ from the Current row, or null when the row has none. */
  rho: number | null
  time: string
  status: unknown
}

export interface CashierWorkload {
  queueId: string
  /** Arithmetic mean of the line's finite ρ values. */
  averageRho: number
  /** Highest finite ρ; a tie keeps the earlier row. */
  peakRho: number
  peakTime: string
  /** API-supplied status of the peak-ρ row, passed through unchanged. */
  peakStatus: unknown
  /** How many finite ρ values were averaged. */
  periodCount: number
}

/**
 * Per-cashier workload for the Current page chart. Source fields are the
 * Current rows' queue_id, rho, time and status. A row without a non-empty
 * queue_id or without a finite ρ is skipped, never counted as zero. Lines keep
 * the order in which they first appear in the rows.
 *
 * Display only: the result must never be fed back into a queueing model.
 */
export function summarizeCashierWorkload(entries: WorkloadEntry[]): CashierWorkload[] {
  const lines = new Map<string, { total: number; line: CashierWorkload }>()
  for (const entry of entries) {
    if (typeof entry.queueId !== 'string' || entry.queueId.trim() === '') continue
    if (entry.rho === null || !Number.isFinite(entry.rho)) continue
    const existing = lines.get(entry.queueId)
    if (!existing) {
      lines.set(entry.queueId, {
        total: entry.rho,
        line: { queueId: entry.queueId, averageRho: entry.rho, peakRho: entry.rho, peakTime: entry.time, peakStatus: entry.status, periodCount: 1 },
      })
      continue
    }
    existing.total += entry.rho
    existing.line.periodCount += 1
    existing.line.averageRho = existing.total / existing.line.periodCount
    if (entry.rho > existing.line.peakRho) {
      existing.line.peakRho = entry.rho
      existing.line.peakTime = entry.time
      existing.line.peakStatus = entry.status
    }
  }
  return [...lines.values()].map(({ line }) => line)
}
