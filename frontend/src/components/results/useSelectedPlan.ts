import { useQuery } from '@tanstack/react-query'
import { listScenarios, type ScenarioOut } from '../../api/scenarios'
import type { OptimizationOut, SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { getSeparateComparison, getWorkflow } from '../../api/workflow'
import { finiteNumber } from '../../lib/results'

export function scenarioRows(scenario: ScenarioOut | null | undefined): OptimizationOut[] {
  const results = scenario?.results
  const rows = results?.results ?? results?.comparison
  return Array.isArray(rows) ? (rows as OptimizationOut[]) : []
}

// 4d: only a scenario the server reports CURRENT may show totals or be used.
export function isCurrentScenario(scenario: ScenarioOut | null | undefined): boolean {
  return scenario?.evidence_status === 'CURRENT'
}

export type SelectedPlan =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'none' }
  | { kind: 'shared'; scenario: ScenarioOut; scenarios: ScenarioOut[]; usable: boolean; target: number | null }
  | { kind: 'separate'; plan: SeparatePlanComparison; comparison: SeparateComparison; usable: boolean; target: number | null }

/**
 * The plan selected for simulation (plans always use the planning file). ``enabled`` is false
 * while a review-only or older file is shown, so no plan, scenario or workflow request is made.
 */
export function useSelectedPlan(analysisId: number, separate: boolean, enabled: boolean): SelectedPlan & { separateComparison?: SeparateComparison; scenarios?: ScenarioOut[] } {
  const workflow = useQuery({ queryKey: ['workflow', analysisId], queryFn: () => getWorkflow(analysisId), enabled: enabled && !separate })
  const scenarios = useQuery({ queryKey: ['scenarios', analysisId], queryFn: () => listScenarios(analysisId), enabled: enabled && !separate })
  const comparison = useQuery({ queryKey: ['separate-comparison', analysisId], queryFn: () => getSeparateComparison(analysisId), enabled: enabled && separate })
  if (!enabled) return { kind: 'none' }
  if (separate) {
    if (comparison.isLoading) return { kind: 'loading' }
    if (comparison.isError || !comparison.data) return { kind: 'error' }
    const plan = comparison.data.plans.find((item) => item.scenario_id === comparison.data.selected_scenario_id)
    if (!plan) return { kind: 'none', separateComparison: comparison.data }
    const usable = plan.valid && !plan.stale
    return { kind: 'separate', plan, comparison: comparison.data, usable, target: usable ? finiteNumber(plan.target) : null, separateComparison: comparison.data }
  }
  if (workflow.isLoading || scenarios.isLoading) return { kind: 'loading' }
  if (workflow.isError || scenarios.isError || !scenarios.data) return { kind: 'error' }
  const list = scenarios.data.scenarios
  // The server drops `scenario` when the selected plan is no longer current; the selection
  // itself (and its evidence status) still names it, so the page can say it is out of date.
  const evidence = workflow.data?.selection_evidence
  const selectedId = workflow.data?.scenario?.id
    ?? evidence?.scenario_id
    ?? finiteNumber(workflow.data?.selection?.params?.scenario_id ?? workflow.data?.selection?.result?.scenario_id)
  const scenario = list.find((item) => Number(item.id) === selectedId)
  if (!scenario) return { kind: 'none', scenarios: list }
  const usable = Boolean(workflow.data?.scenario) && isCurrentScenario(scenario)
  return { kind: 'shared', scenario, scenarios: list, usable, target: usable ? finiteNumber(scenario.settings?.target_utilization) : null }
}
