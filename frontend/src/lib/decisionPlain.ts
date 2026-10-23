/** The stored Decision fields the plain sentence is built from (never computed in the browser). */
export interface PlainDecisionInput {
  status: string | null
  stale?: boolean
  separate: boolean
  failedPeriods?: string[]
  failedCount?: number | null
  totalCount?: number | null
  missing?: string[]
  inadequatePeriods?: string[]
  /** Shared: periods where today's staffing cannot keep up, so the saving cannot be calculated. */
  todayOverloaded?: string[]
}

export interface PlainDecision {
  key: string
  params?: Record<string, string | number>
}

/**
 * The plain answer to "Should we use this plan?" (spec 2026-10-09 §7.9, D12/D13), from the persisted status and the
 * returned reason fields only. Shared Decisions report how many periods failed, not which, so they get the count.
 */
export function plainDecision(input: PlainDecisionInput): PlainDecision | null {
  if (input.stale) return { key: 'decision.plain.stale' }
  switch (input.status) {
    case 'adopt':
      return { key: 'decision.plain.adopt' }
    case 'conditional':
      if (input.separate) return { key: 'decision.plain.conditional_separate' }
      if (input.todayOverloaded && input.todayOverloaded.length > 0) return { key: 'decision.plain.conditional_today_overloaded', params: { periods: input.todayOverloaded.join(', ') } }
      return { key: 'decision.plain.conditional_shared' }
    case 'revise':
      if (input.failedPeriods && input.failedPeriods.length > 0) return { key: input.separate ? 'decision.plain.revise_separate_periods' : 'decision.plain.revise_periods', params: { periods: input.failedPeriods.join(', ') } }
      if (input.failedCount != null && input.totalCount != null) return { key: input.separate ? 'decision.plain.revise_separate_count' : 'decision.plain.revise_count', params: { failed: input.failedCount, total: input.totalCount } }
      return { key: input.separate ? 'decision.plain.revise_separate' : 'decision.plain.revise' }
    case 'insufficient_evidence':
      if (input.missing && input.missing.length > 0) return { key: 'decision.plain.insufficient', params: { missing: input.missing.join('; ') } }
      if (input.inadequatePeriods && input.inadequatePeriods.length > 0) return { key: 'decision.plain.insufficient_periods', params: { periods: input.inadequatePeriods.join(', ') } }
      return { key: 'decision.plain.insufficient_none' }
    default:
      return null
  }
}
