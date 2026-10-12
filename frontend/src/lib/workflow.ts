// Workflow steps in order (spec 2026-10-09 §4). Analysis results lives at /results (U6);
// every other step is a workspace page /analyses/:id/<step>.
export const analysisWorkflow = [
  ['data', 'nav.data_setup'],
  ['plans', 'nav.suggested_plans'],
  ['results', 'nav.analysis_results'],
  ['simulate', 'nav.simulate'],
  ['decision', 'nav.decision'],
  ['reports', 'nav.reports'],
] as const

export function workflowStepHref(step: string, analysisId: number | string): string {
  return step === 'results' ? `/results?analysis=${analysisId}` : `/analyses/${analysisId}/${step}`
}
