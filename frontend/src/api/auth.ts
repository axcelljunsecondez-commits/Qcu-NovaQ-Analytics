import { http } from '../lib/http'
import type { AuthConfig, LoginResponse, MeResponse, UserOut } from './types'

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

export const authConfig = async (): Promise<AuthConfig> =>
  (await http.get<AuthConfig>('/auth/config')).data

export const register = async (email: string, password: string): Promise<{ detail: string }> =>
  (await http.post('/auth/register', { email, password })).data

export const resendVerification = async (email: string): Promise<{ detail: string }> =>
  (await http.post('/auth/resend-verification', { email })).data

export const verifyEmail = async (token: string): Promise<{ detail: string }> =>
  (await http.post('/auth/verify-email', { token })).data

export const forgotPassword = async (email: string): Promise<{ detail: string }> =>
  (await http.post('/auth/forgot-password', { email })).data

export const resetPassword = async (
  token: string,
  newPassword: string,
): Promise<{ detail: string }> =>
  (await http.post('/auth/reset-password', { token, new_password: newPassword })).data

export const googleNonce = async (): Promise<{ nonce: string }> =>
  (await http.post('/auth/google/nonce')).data

export const googleLogin = async (credential: string): Promise<LoginResponse> =>
  (await http.post<LoginResponse>('/auth/google', { credential })).data

export const linkGoogle = async (credential: string): Promise<{ detail: string; user: UserOut }> =>
  (await http.post('/account/auth-identities/google', { credential })).data

export const changePassword = async (
  currentPassword: string,
  newPassword: string,
): Promise<unknown> => {
  const res = await http.post('/account/password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return res.data
}
