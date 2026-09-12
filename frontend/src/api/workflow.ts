import { http } from '../lib/http'
import type { SimMcOut, SimValidateOut, SimulationTrace } from './types'

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
  mc: WorkflowJob<{ results: SimMcOut[] }> | null
  validation: WorkflowJob<{ results: SimValidateOut[] }> | null
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

export async function createWorkflowDecision(
  analysisId: number,
): Promise<{ decision: WorkflowDecision; persisted: boolean }> {
  const { data } = await http.post<{ decision: WorkflowDecision; persisted: boolean }>(
    `/analyses/${analysisId}/workflow/decision`,
  )
  return data
}
