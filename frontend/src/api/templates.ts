import { http } from '../lib/http'
import { downloadReport } from './reports'

export type TemplateStructure = 'shared_queue' | 'separate_queues'
export type TemplateSchema = 'aggregate' | 'events'
export type TemplateFormat = 'csv' | 'xlsx'

export interface TemplateFieldGuideEntry {
  field: string
  meaning: string
  required: string
  example: string
  notes: string
}

export interface TemplateGuide {
  structure: TemplateStructure
  schema: TemplateSchema
  columns: string[]
  example_rows: Array<Record<string, unknown>>
  field_guide: TemplateFieldGuideEntry[]
  accepted_aliases: Record<string, string[]>
}

export async function getTemplateGuide(
  structure: TemplateStructure,
  schema: TemplateSchema,
): Promise<TemplateGuide> {
  const { data } = await http.get<TemplateGuide>('/templates/guide', {
    params: { structure, schema },
  })
  return data
}

export async function downloadTemplate(
  structure: TemplateStructure,
  schema: TemplateSchema,
  format: TemplateFormat,
): Promise<void> {
  const res = await http.get('/templates/download', {
    params: { structure, schema, format },
    responseType: 'blob',
  })
  downloadReport(res.data as Blob, `novaq_${structure}_${schema}_template.${format}`)
}
