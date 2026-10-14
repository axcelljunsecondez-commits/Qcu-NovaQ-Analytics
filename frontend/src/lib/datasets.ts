import type { DatasetOut } from '../api/types'

// B10: the server marks the analysis's current planning dataset with is_current. Responses from
// before B10 carry no such field; then the newest dataset is current, as it was.
export function currentDatasetId(datasets: DatasetOut[] | undefined): number | null {
  if (!datasets || datasets.length === 0) return null
  if (datasets.some((dataset) => dataset.is_current !== undefined && dataset.is_current !== null)) {
    return datasets.find((dataset) => dataset.is_current === true)?.id ?? null
  }
  return datasets[0].id
}

export function isForPlanning(dataset: DatasetOut): boolean {
  return (dataset.purpose ?? 'planning') === 'planning'
}
