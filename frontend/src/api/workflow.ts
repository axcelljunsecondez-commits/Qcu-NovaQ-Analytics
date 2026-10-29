import { http } from '../lib/http'
import type {
  EvidenceReason,
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

export type CheckVerdict = 'pass' | 'fail' | 'insufficient'

/** OD-UX-13: one plan period judged by the full-day run and Many variations (stored by the server). */
export interface FullDayPeriod {
  time: string
  day_run_utilization: number | null
  target_utilization: number | null
  day_run: CheckVerdict
  variations_failure_rate: number | null
  variations_failure_cap: number | null
  variations: CheckVerdict
  verdict: CheckVerdict
}

export interface DecisionFacts {
  current_modeled_cost?: number | null
  selected_modeled_cost?: number | null
  modeled_savings?: number | null
  server_delta?: number
  validation_intervals?: number
  failed_intervals?: number
  /** Selected Separate evidence counts lane-period checks, not periods. */
  validation_checks?: number | null
  failed_checks?: number | null
  failure_rate_cap?: number | null
  today_overloaded_periods?: string[]
  failed_periods?: string[]
  insufficient_periods?: string[]
  periods?: FullDayPeriod[]
  full_day_run?: { id: number; replications: number | null; closing_policy: string | null; service_model: string | null }
}

export type DecisionBasis = 'full_day_run' | 'period_by_period'

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
  facts?: DecisionFacts
  basis?: DecisionBasis
  provenance_warning: string
  /** Selected Separate evidence returns these at the result root. */
  failed_periods?: string[]
  inadequate_periods?: string[]
}

/** 4f/5e: why the recorded selection does or does not yield the selected scenario. */
export interface SelectionEvidence {
  scenario_id: number | null
  evidence_status: string
  evidence_reasons: EvidenceReason[]
}

export interface WorkflowEvidence {
  analysis_id: number
  selection: WorkflowJob | null
  selection_evidence?: SelectionEvidence | null
  scenario: WorkflowScenario | null
  des: WorkflowJob<SimulationTrace> | null
  des_current: WorkflowJob<SimulationTrace> | null
  mc: WorkflowJob<{ results: SimMcOut[] }> | null
  mc_current: WorkflowJob<{ results: SimMcOut[] }> | null
  validation: WorkflowJob<{ results: SimValidateOut[] }> | null
  validation_current: WorkflowJob<WorkflowValidationCurrentResult> | null
  decision: WorkflowJob<WorkflowDecision> | null
  decision_stale: boolean
  /** OD-UX-13: which checks a new shared Decision uses, and the full-day run it would use. */
  decision_basis?: DecisionBasis
  full_day_run_id?: number | null
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
    /** Omitted: the server uses the selected plan's target (spec 2026-10-29). */
    failure_threshold?: number
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

// B3: datasetId reads any processed file of the analysis (read-only); omitted, the planning file.
export async function getObservedWait(analysisId: number, datasetId?: number): Promise<ObservedWaitSummary> {
  const url = `/analyses/${analysisId}/workflow/observed-wait`
  const { data } = datasetId === undefined
    ? await http.get<ObservedWaitSummary>(url)
    : await http.get<ObservedWaitSummary>(url, { params: { dataset_id: datasetId } })
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
