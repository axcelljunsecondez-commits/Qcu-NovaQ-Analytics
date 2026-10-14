import { http } from '../lib/http'

// B4a continuous shared-line run (preview), spec 2026-10-09-b4a-continuous-shared-run-preview.md section 5.
// Fields the page reads are typed as the backend produces them. Times in the result are hours from the
// operating day's start; the horizon is whole minutes since midnight.

export type ClosingPolicy = 'DRAIN' | 'HARD_CUTOFF'
export type ContinuousPlan = 'current' | 'suggested'

export interface ClosingPolicyOut {
  closing_policy: ClosingPolicy | null
  choices: Array<{ value: ClosingPolicy; meaning: string }>
}

export interface ContinuousReason {
  code: string
  problems?: string[]
  detail?: string
  status?: string
  periods?: string[]
}

/** B4b: customer-record uploads run with recorded service times; counts per period with exponential ones. */
export type ServiceModel = 'recorded' | 'exponential'


export interface ContinuousPlanView {
  compatible: boolean
  reasons: ContinuousReason[]
  expected_customers_per_day: number | null
  horizon: { start_minute: number; end_minute: number } | null
  dataset_id: number | null
  scenario_id: number | null
  scenario_name: string | null
  service_model?: ServiceModel | null
  service_fallbacks?: Array<{ period_id: string; uses_period_id: string }>
  /** Counter breaks this run will include (B4c). */
  counter_breaks?: number
}

export interface ContinuousCompatibility {
  closing_policy: ClosingPolicy | null
  plans: Record<ContinuousPlan, ContinuousPlanView>
  default_replications: number
  default_seed: number
  limits: { max_replications: number; max_expected_customers_per_run: number; result_max_bytes: number; status: string }
  preview: true
  model_scope: string
  verdict: null
  verdict_reason: string
}

/** Across-repeat statistics of one value (``null`` = undefined, never 0). */
export interface MetricSummary {
  mean: number | null
  min: number | null
  max: number | null
  n: number
  n_undefined: number
  ci_lower: number | null
  ci_upper: number | null
}

export interface ContinuousSummary {
  replications: number
  customers: {
    arrivals: number
    served: number
    unserved: number
    conserved_in_every_replication: boolean
    per_replication: Record<'arrivals' | 'served' | 'unserved', MetricSummary>
  }
  waiting_time: {
    mean_of_replication_means_hours: MetricSummary
    customer_weighted_mean_hours: { value: number | null }
  }
  metrics: Record<string, MetricSummary>
}

export interface ContinuousResult {
  replications: Array<Record<string, unknown>>
  summary: ContinuousSummary
  provenance: {
    replications: number
    seed: number | null
    closing_policy: ClosingPolicy
    engine_version: string
    inputs: {
      horizon: { start_minute: number; end_minute: number }
      demand_periods: Array<{ period_id: string; start_minute: number; end_minute: number; arrival_rate_per_hour: number }>
      staffing_segments: Array<{ segment_id: string; start_minute: number; end_minute: number; servers: number }>
    }
  }
}

export interface ContinuousRunEvidence {
  id: number
  kind: 'shared_continuous_preview'
  params: {
    analysis_id: number
    plan: ContinuousPlan
    scenario_id: number | null
    dataset_id: number
    replications: number
    seed: number
    closing_policy: ClosingPolicy
    service_model?: ServiceModel
    counter_breaks?: number
  }
  result: ContinuousResult
  created_at: string
}

export interface ContinuousCurrentness {
  setup_matches_current: boolean
  dataset_is_current: boolean
  plan_is_selected: boolean | null
}

export interface ContinuousRunOut extends ContinuousCurrentness {
  evidence: ContinuousRunEvidence
}

export interface ContinuousRunListItem extends ContinuousCurrentness {
  id: number
  plan: ContinuousPlan
  replications: number
  seed: number
  closing_policy: ClosingPolicy
}

export interface ContinuousEvent {
  seq: number
  t: number
  type: string
  queue_len_after: number
  servers_idle_after: number
  servers_busy_after: number
  servers_draining_after: number
  /** Present only in runs with counter breaks (B4c). */
  servers_on_break_after?: number
  breaks_waiting_after?: number
}

export interface ContinuousPeriod {
  period_id: string
  start_hours: number
  end_hours: number
  arrivals: number
  served: number
  unserved: number
  mean_wait_hours: number | null
}

export interface ContinuousPlayback {
  replication_index: number
  playback: {
    events: ContinuousEvent[]
    closing: { closing_hours: number; overrun_hours: number }
  }
  by_period: ContinuousPeriod[]
  preview: true
}

const base = (analysisId: number) => `/analyses/${analysisId}`

export async function getClosingPolicy(analysisId: number): Promise<ClosingPolicyOut> {
  const { data } = await http.get<ClosingPolicyOut>(`${base(analysisId)}/closing-policy`)
  return data
}

export async function putClosingPolicy(analysisId: number, closingPolicy: ClosingPolicy): Promise<{ closing_policy: ClosingPolicy }> {
  const { data } = await http.put<{ closing_policy: ClosingPolicy }>(`${base(analysisId)}/closing-policy`, { closing_policy: closingPolicy })
  return data
}

export async function getContinuousCompatibility(analysisId: number): Promise<ContinuousCompatibility> {
  const { data } = await http.post<ContinuousCompatibility>(`${base(analysisId)}/continuous/compatibility`, {})
  return data
}

export async function createContinuousRun(
  analysisId: number,
  body: { plan: ContinuousPlan; replications: number; seed: number },
): Promise<ContinuousRunOut> {
  const { data } = await http.post<ContinuousRunOut>(`${base(analysisId)}/continuous/runs`, body)
  return data
}

export async function listContinuousRuns(analysisId: number): Promise<{ runs: ContinuousRunListItem[] }> {
  const { data } = await http.get<{ runs: ContinuousRunListItem[] }>(`${base(analysisId)}/continuous/runs`)
  return data
}

export async function getContinuousRun(analysisId: number, runId: number): Promise<ContinuousRunOut> {
  const { data } = await http.get<ContinuousRunOut>(`${base(analysisId)}/continuous/runs/${runId}`)
  return data
}

export async function getContinuousPlayback(analysisId: number, runId: number, index: number): Promise<ContinuousPlayback> {
  const { data } = await http.get<ContinuousPlayback>(`${base(analysisId)}/continuous/runs/${runId}/replications/${index}/playback`)
  return data
}
