import { http } from '../lib/http'
import type { AdminUserOut, CreateUserRequest, UpdateUserRequest } from './types'

export interface UsersResponse {
  users: AdminUserOut[]
}

export interface UserResponse {
  user: AdminUserOut
}

export const listUsers = async (): Promise<UsersResponse> => {
  const res = await http.get<UsersResponse>('/users')
  return res.data
}

export const createUser = async (payload: CreateUserRequest): Promise<UserResponse> => {
  const res = await http.post<UserResponse>('/users', payload)
  return res.data
}

export const updateUser = async (id: number, patch: UpdateUserRequest): Promise<UserResponse> => {
  const res = await http.patch<UserResponse>(`/users/${id}`, patch)
  return res.data
}
