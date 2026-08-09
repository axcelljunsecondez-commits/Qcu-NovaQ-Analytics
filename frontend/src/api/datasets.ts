import { http } from '../lib/http'
import type { DatasetOut } from './types'

export const listDatasets = async (): Promise<{ datasets: DatasetOut[] }> => {
  const res = await http.get<{ datasets: DatasetOut[] }>('/datasets')
  return res.data
}

export const getDataset = async (id: number): Promise<{ dataset: DatasetOut }> => {
  const res = await http.get<{ dataset: DatasetOut }>(`/datasets/${id}`)
  return res.data
}

export const uploadDataset = async (
  file: File,
  name?: string,
): Promise<{ dataset: DatasetOut }> => {
  const formData = new FormData()
  formData.append('file', file)
  if (name) {
    formData.append('name', name)
  }
  const res = await http.post<{ dataset: DatasetOut }>('/datasets', formData)
  return res.data
}

export const deleteDataset = async (id: number): Promise<unknown> => {
  const res = await http.delete(`/datasets/${id}`)
  return res.data
}
