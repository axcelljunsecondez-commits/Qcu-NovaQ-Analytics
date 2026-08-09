import { http } from '../lib/http'

export interface ScenarioOut {
  id: number
  dataset_id: number | null
  name: string
  settings: Record<string, unknown>
  results: Record<string, unknown>
  created_at: string
}

export interface ScenarioIn {
  name: string
  dataset_id?: number | null
  settings?: Record<string, unknown>
  results?: Record<string, unknown>
}

export async function createScenario(payload: ScenarioIn): Promise<{ scenario: ScenarioOut }> {
  const { data } = await http.post<{ scenario: ScenarioOut }>('/scenarios', payload)
  return data
}

export async function listScenarios(): Promise<{ scenarios: ScenarioOut[] }> {
  const { data } = await http.get<{ scenarios: ScenarioOut[] }>('/scenarios')
  return data
}
