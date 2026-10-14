import { http } from '../lib/http'
import type { DecisionFacts } from './workflow'

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

// B8 plan and full reports (spec 2026-10-09-b8 §3): the preview is the report model plus the exact
// section and sheet lists of the files rendered from it.
export type ReportLevel = 'plan' | 'full'

export interface ReportPreview {
  model: {
    report: ReportLevel
    line_type: 'shared' | 'separate'
    cover: { label: string; plan_name: string | null; analysis_name: string | null }
    decision?: { status: string; headline: string; recommendation: string
      missing_evidence?: string[] | null; facts?: DecisionFacts | null }
  }
  contents: { pdf: string[]; excel: string[] }
}

export async function fetchReportPreview(analysisId: number, level: ReportLevel): Promise<ReportPreview> {
  const { data } = await http.get<ReportPreview>(`/analyses/${analysisId}/reports/${level}/preview`)
  return data
}

export async function fetchReportFile(analysisId: number, level: ReportLevel, format: 'pdf' | 'xlsx'): Promise<Blob> {
  const res = await http.get(`/analyses/${analysisId}/reports/${level}.${format}`, { responseType: 'blob' })
  return res.data as Blob
}
