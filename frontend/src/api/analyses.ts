import { http } from '../lib/http'
import { downloadReport } from './reports'
import type { AnalysisCurrentOut, AnalysisProjectOut, DatasetOut, DatasetPreviewOut, DatasetPurpose, QueueSetup, SharedAggregateApplyIn, SharedAggregateApplyOut, SharedAggregatePreviewOut } from './types'

export interface AnalysisInput {
  name: string
  service_type?: string | null
  location_label?: string | null
  queue_setup?: QueueSetup
}

export async function listAnalyses(): Promise<{ analyses: AnalysisProjectOut[] }> {
  const { data } = await http.get<{ analyses: AnalysisProjectOut[] }>('/analyses')
  return data
}

export async function createAnalysis(payload: AnalysisInput): Promise<{ analysis: AnalysisProjectOut }> {
  const { data } = await http.post<{ analysis: AnalysisProjectOut }>('/analyses', payload)
  return data
}

export async function getAnalysis(id: number): Promise<{ analysis: AnalysisProjectOut }> {
  const { data } = await http.get<{ analysis: AnalysisProjectOut }>(`/analyses/${id}`)
  return data
}

export async function patchAnalysis(id: number, payload: Partial<AnalysisInput>): Promise<{ analysis: AnalysisProjectOut }> {
  const { data } = await http.patch<{ analysis: AnalysisProjectOut }>(`/analyses/${id}`, payload)
  return data
}

export async function archiveAnalysis(id: number): Promise<{ analysis: AnalysisProjectOut }> {
  const { data } = await http.post<{ analysis: AnalysisProjectOut }>(`/analyses/${id}/archive`)
  return data
}

export async function listAnalysisDatasets(id: number): Promise<{ datasets: DatasetOut[] }> {
  const { data } = await http.get<{ datasets: DatasetOut[] }>(`/analyses/${id}/datasets`)
  return data
}

export async function uploadAnalysisDataset(
  id: number,
  file: File,
  options: { applySetup?: boolean; purpose?: DatasetPurpose } = {},
): Promise<{ dataset: DatasetOut }> {
  const body = new FormData()
  body.append('file', file)
  // B10: an omitted purpose is a planning file on the server.
  const params = {
    ...(options.applySetup ? { apply_setup: true } : {}),
    ...(options.purpose === 'review' ? { purpose: 'review' } : {}),
  }
  const config = Object.keys(params).length > 0 ? { params } : undefined
  const { data } = await http.post<{ dataset: DatasetOut }>(`/analyses/${id}/datasets`, body, config)
  return data
}

export async function previewAnalysisDataset(id: number, file: File): Promise<DatasetPreviewOut> {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post<DatasetPreviewOut>(`/analyses/${id}/datasets/preview`, body)
  return data
}

export async function previewSharedAggregateDataset(id: number, file: File): Promise<SharedAggregatePreviewOut> {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post<SharedAggregatePreviewOut>(`/analyses/${id}/datasets/shared-aggregate/preview`, body, { params: { purpose: 'planning' } })
  return data
}

export async function applySharedAggregateDataset(id: number, file: File, metadata: SharedAggregateApplyIn): Promise<SharedAggregateApplyOut> {
  const body = new FormData()
  body.append('file', file)
  body.append('metadata', JSON.stringify(metadata))
  const { data } = await http.post<SharedAggregateApplyOut>(`/analyses/${id}/datasets/shared-aggregate/apply`, body, { params: { purpose: 'planning' } })
  return data
}

export async function downloadSetupWorkbook(id: number): Promise<void> {
  const res = await http.get(`/analyses/${id}/setup/workbook`, { responseType: 'blob' })
  downloadReport(res.data as Blob, `novaq_setup_${id}.xlsx`)
}

// B3: datasetId reads any processed file of the analysis (read-only); omitted, the planning file.
export async function getAnalysisCurrent(id: number, datasetId?: number): Promise<AnalysisCurrentOut> {
  const url = `/analyses/${id}/current`
  const { data } = datasetId === undefined
    ? await http.get<AnalysisCurrentOut>(url)
    : await http.get<AnalysisCurrentOut>(url, { params: { dataset_id: datasetId } })
  return data
}

