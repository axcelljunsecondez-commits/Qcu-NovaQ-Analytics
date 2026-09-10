import { http } from '../lib/http'
import type { SegmentInput, SimDesOut, SimMcOut, SimValidateOut, SimulationTrace } from './types'

export interface DesOptions {
  sim_hours?: number
  queue_overload_threshold?: number
  seed?: number | null
  carryover?: boolean
}

export interface TraceOptions {
  trace_hours?: number
  max_events?: number
  seed?: number | null
  carryover?: boolean
}

export interface McOptions {
  num_trials?: number
  failure_threshold?: number
  failure_rate_cap?: number
  seed?: number | null
}

export interface ValidateOptions {
  des_sim_hours?: number
  mc_trials?: number
  mc_failure_threshold?: number
  mc_failure_rate_cap?: number
  seed?: number | null
}

export async function simulateDes(
  segments: SegmentInput[],
  options: DesOptions = {},
): Promise<{ results: SimDesOut[] }> {
  const { data } = await http.post<{ results: SimDesOut[] }>('/simulation/des', {
    segments,
    ...options,
  })
  return data
}

export async function simulateDesTrace(
  segments: SegmentInput[],
  options: TraceOptions = {},
): Promise<SimulationTrace> {
  const { data } = await http.post<SimulationTrace>('/simulation/des/trace', {
    segments,
    ...options,
  })
  return data
}

export async function simulateMc(
  segments: SegmentInput[],
  options: McOptions = {},
): Promise<{ results: SimMcOut[] }> {
  const { data } = await http.post<{ results: SimMcOut[] }>('/simulation/mc', {
    segments,
    ...options,
  })
  return data
}

export async function validateSimulation(
  segments: Record<string, unknown>[],
  options: ValidateOptions = {},
): Promise<{ results: SimValidateOut[] }> {
  const { data } = await http.post<{ results: SimValidateOut[] }>('/simulation/validate', {
    segments,
    ...options,
  })
  return data
}
