import { http } from '../lib/http'
import { downloadReport } from './reports'
import type { AnalysisCurrentOut, AnalysisProjectOut, DatasetOut, DatasetPreviewOut, QueueSetup } from './types'

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
  options: { applySetup?: boolean } = {},
): Promise<{ dataset: DatasetOut }> {
  const body = new FormData()
  body.append('file', file)
  const config = options.applySetup ? { params: { apply_setup: true } } : undefined
  const { data } = await http.post<{ dataset: DatasetOut }>(`/analyses/${id}/datasets`, body, config)
  return data
}

export async function previewAnalysisDataset(id: number, file: File): Promise<DatasetPreviewOut> {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post<DatasetPreviewOut>(`/analyses/${id}/datasets/preview`, body)
  return data
}

export async function downloadSetupWorkbook(id: number): Promise<void> {
  const res = await http.get(`/analyses/${id}/setup/workbook`, { responseType: 'blob' })
  downloadReport(res.data as Blob, `novaq_setup_${id}.xlsx`)
}

export async function getAnalysisCurrent(id: number): Promise<AnalysisCurrentOut> {
  const { data } = await http.get<AnalysisCurrentOut>(`/analyses/${id}/current`)
  return data
}

