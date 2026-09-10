import { http } from '../lib/http'
import type { AnalysisOut } from './types'

export type AnalysisModel = 'mm1' | 'mmc' | 'mgc' | 'mmck' | 'mgck' | 'erlang_a'

export interface AnalysisRequest {
  lambda: number
  mu: number
  c?: number
  variance?: number
  K?: number
  theta?: number
}

export const runAnalysis = async (
  model: AnalysisModel,
  body: AnalysisRequest,
): Promise<AnalysisOut> => {
  const res = await http.post<AnalysisOut>(`/analysis/${model}`, body)
  return res.data
}
