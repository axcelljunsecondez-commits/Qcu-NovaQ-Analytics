import type { AnalysisModel, AnalysisRequest } from '../api/analysis'
import type { AnalysisOut } from '../api/types'

// Quick calculator (spec 2026-10-09 §7.12, plan U9 + B2). Tabs are named by situation and map onto
// NovaQ's explicit analytical models; every number shown comes from a model response.

export const SITUATIONS = ['basic', 'variable', 'limited', 'leaving'] as const
export type Situation = (typeof SITUATIONS)[number]

/** What the user typed, in plain units (minutes where people think in minutes). */
export interface CalculatorInputs {
  lambda: number
  mu: number
  c: number
  /** Typical spread (standard deviation) of service time, minutes. Variable: required; limited: optional. */
  spreadMinutes: number | null
  /** Most customers inside at once, including those being served (K). */
  capacity: number | null
  /** Average patience before a waiting customer leaves, minutes. */
  patienceMinutes: number | null
}

export type InputProblem = 'lambda' | 'mu' | 'c' | 'spread' | 'capacity' | 'patience'

/** Every input the situation needs, checked; an empty list means the inputs can be sent. */
export function inputProblems(situation: Situation, inputs: CalculatorInputs): InputProblem[] {
  const problems: InputProblem[] = []
  if (!Number.isFinite(inputs.lambda) || inputs.lambda < 0) problems.push('lambda')
  if (!Number.isFinite(inputs.mu) || inputs.mu <= 0) problems.push('mu')
  if (!Number.isInteger(inputs.c) || inputs.c < 1) problems.push('c')
  const spread = inputs.spreadMinutes
  if ((situation === 'variable' && (spread === null || !Number.isFinite(spread) || spread < 0))
      || (situation === 'limited' && spread !== null && (!Number.isFinite(spread) || spread < 0))) problems.push('spread')
  const capacity = inputs.capacity
  if (situation === 'limited' && (capacity === null || !Number.isInteger(capacity) || capacity < inputs.c)) problems.push('capacity')
  const patience = inputs.patienceMinutes
  if (situation === 'leaving' && (patience === null || !Number.isFinite(patience) || patience <= 0)) problems.push('patience')
  return problems
}

/** The explicit model for a situation; one counter on the basic tab is M/M/1, as NovaQ's model selection does. */
export function modelFor(situation: Situation, inputs: CalculatorInputs, counters: number): AnalysisModel {
  if (situation === 'variable') return 'mgc'
  if (situation === 'limited') return inputs.spreadMinutes === null ? 'mmck' : 'mgck'
  if (situation === 'leaving') return 'erlang_a'
  return counters === 1 ? 'mm1' : 'mmc'
}

/** The request body: variance in hours² from the spread in minutes, θ per hour from the patience in minutes. */
export function requestFor(situation: Situation, inputs: CalculatorInputs, counters: number): AnalysisRequest {
  const body: AnalysisRequest = { lambda: inputs.lambda, mu: inputs.mu, c: counters }
  if (inputs.spreadMinutes !== null && (situation === 'variable' || situation === 'limited')) {
    body.variance = (inputs.spreadMinutes / 60) ** 2
  }
  if (situation === 'limited' && inputs.capacity !== null) body.K = inputs.capacity
  if (situation === 'leaving' && inputs.patienceMinutes !== null) body.theta = 60 / inputs.patienceMinutes
  return body
}

/** One fewer and one more counter, when that is a valid input: never 0 counters, never more counters than places. */
export function neighbourCounters(situation: Situation, inputs: CalculatorInputs): { fewer: number | null; more: number | null } {
  const fewer = inputs.c - 1 >= 1 ? inputs.c - 1 : null
  const limit = situation === 'limited' ? inputs.capacity ?? inputs.c : Number.POSITIVE_INFINITY
  return { fewer, more: inputs.c + 1 <= limit ? inputs.c + 1 : null }
}

export type KeepUp = 'yes' | 'no' | 'not_calculated'

export interface CalculatorSummary {
  /** Average wait in line, minutes; null when the model gives none. */
  waitMinutes: number | null
  /** Share of time counters are busy (0-1); null when not given. */
  busy: number | null
  /** People waiting on average. */
  waiting: number | null
  /** Basic and variable tabs only: whether the line settles. */
  keepUp: KeepUp | null
  /** Limited tab: share of arriving customers turned away. */
  turnedAway: number | null
  /** Leaving tab: share of arriving customers who leave before service. */
  leaving: number | null
}

// Float tolerance for "load at or above capacity", as NovaQ's utilization thresholds use.
const LOAD_TOLERANCE = 1e-9

/**
 * Reads one model response without adding anything. "Can counters keep up?" comes from the returned load
 * (rho >= 1), not from the error text: the engine can fail for numerical reasons while rho < 1, and then the
 * honest answer is "not calculated".
 */
export function summarize(situation: Situation, result: AnalysisOut): CalculatorSummary {
  const open = situation === 'basic' || situation === 'variable'
  const busy = situation === 'leaving' ? result.rho_effective ?? null : result.rho
  let keepUp: KeepUp | null = null
  if (open) {
    keepUp = result.stable ? 'yes' : Number.isFinite(result.rho) && result.rho >= 1 - LOAD_TOLERANCE ? 'no' : 'not_calculated'
  }
  return {
    waitMinutes: result.stable && result.Wq !== null ? result.Wq * 60 : null,
    busy: result.stable ? busy : null,
    waiting: result.stable ? result.Lq : null,
    keepUp,
    turnedAway: situation === 'limited' && result.stable ? result.blocking_probability ?? null : null,
    leaving: situation === 'leaving' && result.stable ? result.abandonment_rate ?? null : null,
  }
}
