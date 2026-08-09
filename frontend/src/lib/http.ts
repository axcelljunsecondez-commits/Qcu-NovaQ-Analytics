import axios from 'axios'
import { queryClient } from './queryClient'
import { getCsrfToken, hasSessionCookie } from './csrf'

export const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toUpperCase()
  if (method !== 'GET' && hasSessionCookie()) {
    config.headers['X-CSRF-Token'] = getCsrfToken() ?? ''
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const status = (error as { response?: { status?: number } }).response?.status
    const url = (error as { config?: { url?: string } }).config?.url ?? ''
    if (status === 401 && !url.includes('/auth/me')) {
      void queryClient.invalidateQueries({ queryKey: ['me'] })
    }
    return Promise.reject(error)
  },
)
