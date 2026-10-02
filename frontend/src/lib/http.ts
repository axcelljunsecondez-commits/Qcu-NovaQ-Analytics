import axios from 'axios'
import type { QueryClient } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import { getCsrfToken } from './csrf'

const CLIENT_PROTOCOL_HEADER = 'X-NovaQ-Client-Protocol'
const CLIENT_PROTOCOL = '2'
const CLIENT_UPDATE_CODE = 'client_update_required'

let clientUpdateRequired = false
let activeQueryClient: QueryClient = queryClient
const clientUpdateListeners = new Set<() => void>()

export function isClientUpdateRequired(): boolean {
  return clientUpdateRequired
}

export function subscribeClientUpdate(listener: () => void): () => void {
  clientUpdateListeners.add(listener)
  return () => clientUpdateListeners.delete(listener)
}

export function bindActiveQueryClient(client: QueryClient): () => void {
  activeQueryClient = client
  if (clientUpdateRequired) {
    void client.cancelQueries()
    client.clear()
  }
  return () => {
    if (activeQueryClient === client) activeQueryClient = queryClient
  }
}

function requireClientUpdate(): void {
  if (clientUpdateRequired) return
  clientUpdateRequired = true
  void activeQueryClient.cancelQueries()
  activeQueryClient.clear()
  for (const listener of clientUpdateListeners) listener()
}

function blockedRequest(): Error {
  return new Error('NovaQ has been updated. Reload the application.')
}

async function isClientUpdateCode(data: unknown): Promise<boolean> {
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try {
      return isClientUpdateCode(JSON.parse(await data.text()))
    } catch {
      return false
    }
  }
  return typeof data === 'object' && data !== null && 'code' in data && data.code === CLIENT_UPDATE_CODE
}

// Reset only between isolated frontend tests; production never clears this state without a reload.
export function resetClientUpdateForTests(): void {
  if (import.meta.env.MODE !== 'test') return
  clientUpdateRequired = false
  activeQueryClient = queryClient
  for (const listener of clientUpdateListeners) listener()
}

export const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  if (clientUpdateRequired) return Promise.reject(blockedRequest())
  config.headers[CLIENT_PROTOCOL_HEADER] = CLIENT_PROTOCOL
  const method = (config.method ?? 'get').toUpperCase()
  if (method !== 'GET') {
    const csrf = getCsrfToken()
    if (csrf) {
      config.headers['X-CSRF-Token'] = csrf
    }
  }
  return config
})

http.interceptors.response.use(
  (response) => clientUpdateRequired ? Promise.reject(blockedRequest()) : response,
  async (error: unknown) => {
    const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response
    if (response?.status === 403 && await isClientUpdateCode(response.data)) {
      requireClientUpdate()
    }
    if (clientUpdateRequired) return Promise.reject(blockedRequest())
    const status = response?.status
    const url = (error as { config?: { url?: string } }).config?.url ?? ''
    if (status === 401 && !url.includes('/auth/me')) {
      void activeQueryClient.invalidateQueries({ queryKey: ['me'] })
    }
    return Promise.reject(error)
  },
)
