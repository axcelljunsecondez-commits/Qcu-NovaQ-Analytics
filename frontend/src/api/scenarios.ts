import { http } from '../lib/http'
import type { EvidenceReason } from './types'

export interface ScenarioOut {
  id: number | string
  analysis_id: number | null
  dataset_id: number | null
  name: string
  settings: Record<string, unknown>
  results: Record<string, unknown>
  created_at: string
  provenance?: string
  roi_unavailable_reason?: string | null
  // 4c: only 'CURRENT' allows current-only totals and selection. Anything else, including an
  // absent value, is not current.
  evidence_status?: string | null
  evidence_reasons?: EvidenceReason[] | null
}

export interface ScenarioIn {
  name: string
  dataset_id?: number | null
  analysis_id?: number | null
  settings?: Record<string, unknown>
  results?: Record<string, unknown>
}

export async function createScenario(payload: ScenarioIn): Promise<{ scenario: ScenarioOut }> {
  const { data } = await http.post<{ scenario: ScenarioOut }>('/scenarios', payload)
  return data
}

export async function listScenarios(analysisId?: number): Promise<{ scenarios: ScenarioOut[] }> {
  const { data } = await http.get<{ scenarios: ScenarioOut[] }>('/scenarios', {
    params: analysisId ? { analysis_id: analysisId } : undefined,
  })
  return data
}
