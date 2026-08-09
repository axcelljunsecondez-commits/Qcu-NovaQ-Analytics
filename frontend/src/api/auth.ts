import { http } from '../lib/http'
import type { LoginResponse, MeResponse } from './types'

export const me = async (): Promise<MeResponse> => {
  const res = await http.get<MeResponse>('/auth/me')
  return res.data
}

export const login = async (body: { email: string; password: string }): Promise<LoginResponse> => {
  const res = await http.post<LoginResponse>('/auth/login', body)
  return res.data
}

export const logout = async (): Promise<unknown> => {
  const res = await http.post('/auth/logout')
  return res.data
}
