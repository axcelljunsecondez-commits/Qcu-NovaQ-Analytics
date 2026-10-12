// What a Queue simulation page needs to know about the analysis and its stored runs
// (spec 2026-10-09 §7.8, D28). Runs are read from the workflow evidence only.
import type { AnalysisProjectOut, SelectedDesResult, SimulationTrace } from '../../api/types'
import type { WorkflowEvidence, WorkflowScenario } from '../../api/workflow'
import { evidenceStatusKey } from '../../lib/format'
import { isSelectedDesResult } from '../../lib/simulationEvidence'

export type SimulationPageName = 'results' | 'replay' | 'checks'
export type RunChoice = 'current' | 'suggested'

export interface SimulationContext {
  analysisId: number
  analysis: AnalysisProjectOut
  workflow: WorkflowEvidence
  separate: boolean
  scenario: WorkflowScenario | null
  /** A separate-lines plan saved by Suggested plans (schedule snapshot, schema 2). */
  selectedSeparate: boolean
  planTarget: number | null
  /** Separate lines with one typical day: the plan runs as one continuous day. */
  representativeDay: boolean
  selectionUnavailable: { scenarioId: number | null; statusKey: string; detail: string | null } | null
}

export function buildContext(analysisId: number, analysis: AnalysisProjectOut, workflow: WorkflowEvidence): SimulationContext {
  const setup = analysis.queue_setup
  const separate = setup.queue_structure === 'separate_queues'
  const scenario = workflow.scenario ?? null
  const calculation = (scenario?.settings?.calculation ?? {}) as { schema_version?: unknown; options?: { target_utilization?: unknown } }
  const rawTarget = calculation.options?.target_utilization
  const planTarget = typeof rawTarget === 'number' && Number.isFinite(rawTarget) && rawTarget > 0 && rawTarget <= 1 ? rawTarget : null
  // 4f/5e: a recorded selection whose scenario is withheld names the unavailable evidence and why.
  const evidence = workflow.selection_evidence
  const statusKey = !scenario && evidence && evidence.evidence_status !== 'CURRENT' ? evidenceStatusKey(evidence.evidence_status) : null
  return {
    analysisId,
    analysis,
    workflow,
    separate,
    scenario,
    selectedSeparate: separate && scenario !== null && calculation.schema_version === 2,
    planTarget,
    representativeDay: separate && setup.event_period_basis === 'representative_day',
    selectionUnavailable: statusKey && evidence
      ? { scenarioId: evidence.scenario_id, statusKey, detail: evidence.evidence_reasons?.[0]?.detail ?? null }
      : null,
  }
}

/** The plan's stored run: the selected separate plan's run, or the legacy shared run. */
export function suggestedRun(context: SimulationContext): { kind: 'separate'; result: SelectedDesResult } | { kind: 'legacy'; result: SimulationTrace } | null {
  const evidence = context.workflow.des
  if (!evidence || !context.scenario) return null
  if (context.selectedSeparate) {
    return isSelectedDesResult(evidence.result) && evidence.result.scenario_id === context.scenario.id
      ? { kind: 'separate', result: evidence.result }
      : null
  }
  return context.separate ? null : { kind: 'legacy', result: evidence.result as SimulationTrace }
}

export function currentRun(context: SimulationContext): SimulationTrace | null {
  return (context.workflow.des_current?.result as SimulationTrace | undefined) ?? null
}

/**
 * Whether the chosen run models the setup's breaks. Only the continuous day of a selected
 * separate-lines plan places them in time. A date-by-date plan run simulates each period alone for
 * many hours, so a break is a small share of the run and its effect is understated. The Current run
 * and the legacy shared run have no breaks at all (simulation.py).
 */
export function breakNoticeKey(context: SimulationContext, run: RunChoice): string | null {
  if ((context.analysis.queue_setup.breaks ?? []).length === 0) return null
  if (run === 'suggested' && context.selectedSeparate) {
    return context.representativeDay ? null : 'simulation.breaks_understated_per_date'
  }
  return 'simulation.breaks_not_modeled'
}

/** Which kind of run backs the chosen view, said on screen (spec §7.8 engine coverage). */
export function runBasisKey(context: SimulationContext, run: RunChoice): string {
  if (run === 'suggested' && context.selectedSeparate) {
    return context.representativeDay ? 'simulation.run_basis_continuous' : 'simulation.run_basis_per_period'
  }
  return 'simulation.run_basis_per_period'
}

/** The run the page shows: what the address asks for, falling back to what exists. */
export function defaultRun(context: SimulationContext): RunChoice {
  return context.scenario ? 'suggested' : 'current'
}

export function simulationHref(page: SimulationPageName, params: URLSearchParams): string {
  const query = params.toString()
  return `/simulation/${page}${query ? `?${query}` : ''}`
}
