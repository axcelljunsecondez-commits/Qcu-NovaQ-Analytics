import { http } from '../lib/http'

export type ReportKind = 'datasets' | 'scenarios'
export type ReportFormat = 'pdf' | 'excel'

export function reportFileExtension(format: ReportFormat): 'pdf' | 'xlsx' {
  return format === 'excel' ? 'xlsx' : 'pdf'
}

export async function fetchReport(kind: ReportKind, id: number, format: ReportFormat, analysisId?: number): Promise<Blob> {
  const res = await http.get(`/reports/${kind}/${id}/${format}`, {
    responseType: 'blob',
    params: analysisId ? { analysis_id: analysisId } : undefined,
  })
  return res.data as Blob
}

export async function fetchSelectedPreview(analysisId: number): Promise<{ model: Record<string, unknown> }> {
  const { data } = await http.get<{ model: Record<string, unknown> }>(
    `/reports/analyses/${analysisId}/selected/preview`,
  )
  return data
}

export async function fetchSelectedReport(analysisId: number, format: ReportFormat): Promise<Blob> {
  const res = await http.get(`/reports/analyses/${analysisId}/selected/${format}`, {
    responseType: 'blob',
  })
  return res.data as Blob
}

export function downloadReport(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
