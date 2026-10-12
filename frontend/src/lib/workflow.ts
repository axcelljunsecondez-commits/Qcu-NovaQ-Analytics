// Workflow steps in order (spec 2026-10-09 §4). Analysis results lives at /results (U6) and
// Queue simulation at /simulation/results (U7a); every other step is a workspace page.
export const analysisWorkflow = [
  ['data', 'nav.data_setup'],
  ['plans', 'nav.suggested_plans'],
  ['results', 'nav.analysis_results'],
  ['simulate', 'nav.queue_simulation'],
  ['decision', 'nav.decision'],
  ['reports', 'nav.reports'],
] as const

export function workflowStepHref(step: string, analysisId: number | string): string {
  if (step === 'results') return `/results?analysis=${analysisId}`
  if (step === 'simulate') return `/simulation/results?analysis=${analysisId}`
  return `/analyses/${analysisId}/${step}`
}
