// What a Queue simulation page needs to know about the analysis and its stored runs
// (spec 2026-10-09 §7.8, D28). Runs are read from the workflow evidence only.
import type { AnalysisProjectOut, QueueSetup, SelectedDesResult, SimulationTrace } from '../../api/types'
import type { WorkflowEvidence, WorkflowScenario } from '../../api/workflow'
import { evidenceStatusKey } from '../../lib/format'
import { dayOrigin } from '../../lib/replay'
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
  /** B13: separate lines with per-date data and operating segments: the plan runs one continuous day per date. */
  perDateDays: boolean
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
    perDateDays: separate && setup.event_period_basis === 'per_date' && dayOrigin(setup) !== null,
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

/** Resolve the displayed plan's own breaks without replacing the Current baseline. */
export function runSetup(context: SimulationContext, run: RunChoice): QueueSetup {
  const setup = context.analysis.queue_setup
  if (run !== 'suggested') return setup
  const calculation = context.scenario?.settings?.calculation as { plan_breaks?: QueueSetup['breaks'] } | undefined
  return Array.isArray(calculation?.plan_breaks) ? { ...setup, breaks: calculation.plan_breaks } : setup
}

/** Historical mocked/stored runs without the execution marker must not claim break support. */
export function currentModelsBreaks(context: SimulationContext): boolean {
  const stored = currentRun(context)
  return context.separate && (context.analysis.queue_setup.breaks ?? []).length > 0 &&
    (stored === null || stored.break_policy === 'scheduled_windows_nonpreemptive_v1')
}

function clockSeconds(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(value.trim())
  return match ? Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3] ?? 0) : null
}

/** K-PR58-3: an earlier NovaQ Apply rewrote these Setup break starts and kept the uploaded start in original_start_time. */
export function setupBreaksMovedEarlier(context: SimulationContext): boolean {
  return (context.analysis.queue_setup.breaks ?? []).some((entry) => {
    const original = entry.original_start_time
    if (typeof original !== 'string' || original.trim() === '') return false
    const before = clockSeconds(original)
    const now = clockSeconds(entry.scheduled_start_time)
    return before === null || now === null ? original.trim() !== entry.scheduled_start_time.trim() : before !== now
  })
}

export function breakNoticeKey(context: SimulationContext, run: RunChoice): string | null {
  if ((runSetup(context, run).breaks ?? []).length === 0) return null
  if (run === 'current' && currentModelsBreaks(context)) return null
  if (run === 'suggested' && context.selectedSeparate) {
    return context.representativeDay || context.perDateDays ? null : 'simulation.breaks_understated_per_date'
  }
  return 'simulation.breaks_not_modeled'
}

/**
 * Which kind of run backs the chosen view, said on screen (spec §7.8 engine coverage). The separate-lines
 * Current run is one continuous SimPy run over the baseline Setup's periods (simulation.py
 * _simulate_parallel_segments_core, review K-UC-3), one per date on per-date data (C-PD); the shared Current run and the legacy shared run
 * simulate one period at a time (_simulate_segments_core).
 */
export function runBasisKey(context: SimulationContext, run: RunChoice): string {
  if (run === 'suggested' && context.selectedSeparate) {
    if (context.representativeDay) return 'simulation.run_basis_continuous'
    return context.perDateDays ? 'simulation.run_basis_continuous_per_date' : 'simulation.run_basis_per_period'
  }
  if (run === 'current' && context.separate) {
    if (currentModelsBreaks(context)) {
      return context.perDateDays ? 'simulation.run_basis_per_date_baseline_breaks' : 'simulation.run_basis_baseline_breaks'
    }
    return context.perDateDays ? 'simulation.run_basis_continuous_per_date' : 'simulation.run_basis_continuous_no_breaks'
  }
  return 'simulation.run_basis_per_period'
}

/** Whether the Current basis needs the separate "No breaks" chip: its basis text does not already say it. */
export function currentNoBreaksChip(context: SimulationContext, run: RunChoice): boolean {
  return run === 'current' && context.separate && context.perDateDays && !currentModelsBreaks(context)
}

/** The run the page shows: what the address asks for, falling back to what exists. */
export function defaultRun(context: SimulationContext): RunChoice {
  return context.scenario ? 'suggested' : 'current'
}

export function simulationHref(page: SimulationPageName, params: URLSearchParams): string {
  const query = params.toString()
  return `/simulation/${page}${query ? `?${query}` : ''}`
}
