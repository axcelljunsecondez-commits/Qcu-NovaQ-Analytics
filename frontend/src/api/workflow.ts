import { http } from '../lib/http'
import type {
  ObservedWaitSummary,
  SelectedDesResult,
  SelectedDecision,
  SelectedMcResult,
  SelectedValidationResult,
  SeparateComparison,
  SimMcOut,
  SimValidateOut,
  SimulationTrace,
} from './types'

export interface WorkflowJob<T = Record<string, unknown>> {
  id: number
  kind: string
  status: string
  params: Record<string, unknown>
  result: T
  created_at: string
  finished_at: string | null
}

export interface WorkflowScenario {
  id: number
  name: string
  dataset_id: number
  provenance: 'verified_snapshot'
  settings?: Record<string, unknown>
}

export interface WorkflowValidationCurrentRow {
  time: string
  queue_id: string
  mc_failure_rate: number | null
  mc_failure_rate_adequate: boolean | null
  failure_rate_cap: number
  validation_verdict: 'pass' | 'fail' | 'inadequate' | 'missing'
}

export interface WorkflowValidationCurrentResult {
  results: WorkflowValidationCurrentRow[]
  verdict: {
    status: 'pass' | 'fail' | 'insufficient'
    failed: Array<{ time: string; queue_id: string } | [string, string]>
    inadequate: Array<{ time: string; queue_id: string } | [string, string]>
    total: number
  }
  mc_job_id: number
  provenance: string
}

export interface WorkflowDecision {
  status: 'insufficient_evidence' | 'revise' | 'adopt' | 'conditional'
  headline: string
  recommendation: string
  rationale: string[]
  missing_evidence: string[]
  scenario_id: number | null
  scenario_name: string | null
  dataset_id: number | null
  evidence_ids: Record<string, number | null>
  facts?: Record<string, number>
  provenance_warning: string
}

export interface WorkflowEvidence {
  analysis_id: number
  selection: WorkflowJob | null
  scenario: WorkflowScenario | null
  des: WorkflowJob<SimulationTrace> | null
  des_current: WorkflowJob<SimulationTrace> | null
  mc: WorkflowJob<{ results: SimMcOut[] }> | null
  mc_current: WorkflowJob<{ results: SimMcOut[] }> | null
  validation: WorkflowJob<{ results: SimValidateOut[] }> | null
  validation_current: WorkflowJob<WorkflowValidationCurrentResult> | null
  decision: WorkflowJob<WorkflowDecision> | null
  decision_stale: boolean
}

export async function getWorkflow(analysisId: number): Promise<WorkflowEvidence> {
  const { data } = await http.get<WorkflowEvidence>(`/analyses/${analysisId}/workflow`)
  return data
}

export async function selectWorkflowScenario(
  analysisId: number,
  scenarioId: number,
): Promise<{ selection: WorkflowJob }> {
  const { data } = await http.post<{ selection: WorkflowJob }>(
    `/analyses/${analysisId}/workflow/selection`,
    { scenario_id: scenarioId },
  )
  return data
}

export async function runWorkflowDes(
  analysisId: number,
  options: {
    sim_hours: number
    queue_overload_threshold: number
    max_events: number
    seed: number | null
    carryover: boolean
  },
): Promise<{ evidence: WorkflowJob<SimulationTrace> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<SimulationTrace> }>(
    `/analyses/${analysisId}/workflow/simulation/des`,
    options,
  )
  return data
}

export async function runWorkflowDesCurrent(
  analysisId: number,
  options: {
    sim_hours: number
    queue_overload_threshold: number
    max_events: number
    seed: number | null
    carryover: boolean
  },
): Promise<{ evidence: WorkflowJob<SimulationTrace> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<SimulationTrace> }>(
    `/analyses/${analysisId}/workflow/simulation/des/current`,
    options,
  )
  return data
}

export async function runWorkflowMc(
  analysisId: number,
  options: {
    num_trials: number
    failure_threshold: number
    failure_rate_cap: number
    seed: number | null
  },
): Promise<{ evidence: WorkflowJob<{ results: SimMcOut[] }> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<{ results: SimMcOut[] }> }>(
    `/analyses/${analysisId}/workflow/simulation/mc`,
    options,
  )
  return data
}

export async function runWorkflowMcCurrent(
  analysisId: number,
  options: {
    num_trials: number
    failure_threshold: number
    failure_rate_cap: number
    seed: number | null
  },
): Promise<{ evidence: WorkflowJob<{ results: SimMcOut[] }> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<{ results: SimMcOut[] }> }>(
    `/analyses/${analysisId}/workflow/simulation/mc/current`,
    options,
  )
  return data
}

export async function runWorkflowValidation(
  analysisId: number,
  options: {
    des_sim_hours: number
    mc_trials: number
    mc_failure_threshold: number
    mc_failure_rate_cap: number
    seed: number | null
  },
): Promise<{ evidence: WorkflowJob<{ results: SimValidateOut[] }> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<{ results: SimValidateOut[] }> }>(
    `/analyses/${analysisId}/workflow/simulation/validation`,
    options,
  )
  return data
}

export async function runWorkflowValidationCurrent(
  analysisId: number,
): Promise<{ evidence: WorkflowJob<WorkflowValidationCurrentResult> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<WorkflowValidationCurrentResult> }>(
    `/analyses/${analysisId}/workflow/simulation/validation/current`,
  )
  return data
}

export async function createWorkflowDecision(
  analysisId: number,
): Promise<{ decision: WorkflowDecision; persisted: boolean }> {
  const { data } = await http.post<{ decision: WorkflowDecision; persisted: boolean }>(
    `/analyses/${analysisId}/workflow/decision`,
  )
  return data
}

export async function getSeparateComparison(
  analysisId: number,
): Promise<SeparateComparison> {
  const { data } = await http.get<SeparateComparison>(
    `/analyses/${analysisId}/workflow/comparison/separate`,
  )
  return data
}

export async function getObservedWait(analysisId: number): Promise<ObservedWaitSummary> {
  const { data } = await http.get<ObservedWaitSummary>(
    `/analyses/${analysisId}/workflow/observed-wait`,
  )
  return data
}

export async function runSelectedDes(
  analysisId: number,
  options: { seed?: number | null } = {},
): Promise<{ evidence: WorkflowJob<SelectedDesResult> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<SelectedDesResult> }>(
    `/analyses/${analysisId}/workflow/simulation/des/selected`,
    options,
  )
  return data
}

export async function runSelectedMc(
  analysisId: number,
  options: {
    num_trials?: number
    failure_threshold?: number
    failure_rate_cap?: number
    seed?: number | null
  } = {},
): Promise<{ evidence: WorkflowJob<SelectedMcResult> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<SelectedMcResult> }>(
    `/analyses/${analysisId}/workflow/simulation/mc/selected`,
    options,
  )
  return data
}

export async function runSelectedValidation(
  analysisId: number,
): Promise<{ evidence: WorkflowJob<SelectedValidationResult> }> {
  const { data } = await http.post<{ evidence: WorkflowJob<SelectedValidationResult> }>(
    `/analyses/${analysisId}/workflow/simulation/validation/selected`,
    {},
  )
  return data
}

export async function runSelectedDecision(
  analysisId: number,
): Promise<{ decision: SelectedDecision; persisted: boolean; evidence: WorkflowJob<SelectedDecision> }> {
  const { data } = await http.post<{
    decision: SelectedDecision; persisted: boolean; evidence: WorkflowJob<SelectedDecision>
  }>(
    `/analyses/${analysisId}/workflow/decision/selected`,
    {},
  )
  return data
}
