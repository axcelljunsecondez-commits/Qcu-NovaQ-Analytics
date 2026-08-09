import { http } from '../lib/http'
import type { DatasetOut } from './types'

export const listDatasets = async (): Promise<{ datasets: DatasetOut[] }> => {
  const res = await http.get<{ datasets: DatasetOut[] }>('/datasets')
  return res.data
}
