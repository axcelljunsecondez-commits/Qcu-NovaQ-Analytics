export const analysisDestinations = ['results', 'reports', 'simulation/results', 'simulation/replay', 'simulation/checks'] as const
export type AnalysisDestination = (typeof analysisDestinations)[number]

// Only these authenticated areas may receive the continuation from New analysis.
export function parseAnalysisDestination(value: string | null): AnalysisDestination | null {
  return analysisDestinations.find((destination) => destination === value) ?? null
}

export function analysisDestinationHref(destination: AnalysisDestination, id: number): string {
  return `/${destination}?analysis=${id}`
}
