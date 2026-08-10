import { http } from '../lib/http'

export type ReportKind = 'datasets' | 'scenarios'
export type ReportFormat = 'pdf' | 'excel'

export async function fetchReport(kind: ReportKind, id: number, format: ReportFormat): Promise<Blob> {
  const res = await http.get(`/reports/${kind}/${id}/${format}`, { responseType: 'blob' })
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
