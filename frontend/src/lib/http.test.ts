import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import { login, googleLogin, googleNonce } from '../api/auth'
import { uploadDataset } from '../api/datasets'
import { fetchReport, fetchSelectedReport } from '../api/reports'
import {
  bindActiveQueryClient,
  http,
  isClientUpdateRequired,
  resetClientUpdateForTests,
  subscribeClientUpdate,
} from './http'

const adapterMock = vi.fn(async (config: InternalAxiosRequestConfig) => ({
  data: {},
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
}))

beforeEach(() => {
  resetClientUpdateForTests()
  adapterMock.mockClear()
  http.defaults.adapter = adapterMock as never
})

afterEach(() => {
  resetClientUpdateForTests()
  document.cookie = 'novaq_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

describe('http request interceptors', () => {
  it('attaches X-CSRF-Token to POST when the csrf cookie is present', async () => {
    document.cookie = 'novaq_csrf=test-token'
    await http.post('/anything')
    const config = adapterMock.mock.calls[0][0]
    expect(config.headers['X-CSRF-Token']).toBe('test-token')
    expect(config.headers['X-NovaQ-Client-Protocol']).toBe('2')
  })

  it('sends no X-CSRF-Token on GET', async () => {
    document.cookie = 'novaq_csrf=test-token'
    await http.get('/anything')
    const config = adapterMock.mock.calls[0][0]
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
    expect(config.headers['X-NovaQ-Client-Protocol']).toBe('2')
  })

  it('marks dataset uploads and blob downloads with the protocol', async () => {
    await uploadDataset(new File(['time,arrivals\n08:00,1'], 'sample.csv', { type: 'text/csv' }))
    await fetchReport('datasets', 8, 'pdf')
    await fetchSelectedReport(7, 'excel')
    expect(adapterMock.mock.calls.map(([config]) => [config.url, config.headers['X-NovaQ-Client-Protocol']])).toEqual([
      ['/datasets', '2'],
      ['/reports/datasets/8/pdf', '2'],
      ['/reports/analyses/7/selected/excel', '2'],
    ])
    expect(adapterMock.mock.calls[0][0].data).toBeInstanceOf(FormData)
    expect(adapterMock.mock.calls[1][0].responseType).toBe('blob')
    expect(adapterMock.mock.calls[2][0].responseType).toBe('blob')
  })

  it('marks password and Google login paths with the protocol', async () => {
    await login({ email: 'user@example.com', password: 'password' })
    await googleNonce()
    await googleLogin('credential')
    expect(adapterMock.mock.calls.map(([config]) => [config.url, config.headers['X-NovaQ-Client-Protocol']])).toEqual([
      ['/auth/login', '2'],
      ['/auth/google/nonce', '2'],
      ['/auth/google', '2'],
    ])
  })
})

describe('client update fence', () => {
  const updateRequired = {
    response: { status: 403, data: { code: 'client_update_required' } },
  }

  it('locks on only the exact 403 code, clears the active rendered query cache and blocks later calls', async () => {
    const active = new QueryClient()
    active.setQueryData(['scenarios', 7], { scenarios: [{ id: 1 }] })
    const unbind = bindActiveQueryClient(active)
    const listener = vi.fn()
    const unsubscribe = subscribeClientUpdate(listener)
    try {
      adapterMock.mockRejectedValueOnce({ response: { status: 403, data: { code: 'csrf_failed' } } })
      await expect(http.get('/csrf')).rejects.toBeTruthy()
      expect(isClientUpdateRequired()).toBe(false)
      expect(active.getQueryData(['scenarios', 7])).toBeDefined()

      adapterMock.mockRejectedValueOnce(updateRequired)
      await expect(http.get('/scenarios')).rejects.toThrow('Reload the application')
      expect(isClientUpdateRequired()).toBe(true)
      expect(active.getQueryData(['scenarios', 7])).toBeUndefined()
      expect(listener).toHaveBeenCalledOnce()

      await expect(http.post('/analyses/7/workflow/selection')).rejects.toThrow('Reload the application')
      await expect(login({ email: 'user@example.com', password: 'password' })).rejects.toThrow('Reload the application')
      await expect(googleNonce()).rejects.toThrow('Reload the application')
      await expect(googleLogin('credential')).rejects.toThrow('Reload the application')
      expect(adapterMock).toHaveBeenCalledTimes(2)
      expect(listener).toHaveBeenCalledOnce()
    } finally {
      unsubscribe()
      unbind()
      active.clear()
    }
  })

  it('discards a response that finishes after a client update refusal', async () => {
    let finishSlow!: (response: { data: object; status: number; statusText: string; headers: object; config: InternalAxiosRequestConfig }) => void
    adapterMock.mockImplementationOnce(() => new Promise((resolve) => { finishSlow = resolve }))
    const slowResult = http.get('/slow').then(() => 'accepted', () => 'discarded')
    await vi.waitFor(() => expect(adapterMock).toHaveBeenCalledTimes(1))

    adapterMock.mockRejectedValueOnce(updateRequired)
    await expect(http.get('/trigger')).rejects.toThrow('Reload the application')
    finishSlow({ data: { current: 123 }, status: 200, statusText: 'OK', headers: {}, config: adapterMock.mock.calls[0][0] })
    expect(await slowResult).toBe('discarded')
  })

  it('recognizes an exact update refusal returned as a report-download Blob', async () => {
    adapterMock.mockRejectedValueOnce({
      response: {
        status: 403,
        data: new Blob([JSON.stringify({ code: 'client_update_required' })], { type: 'application/json' }),
      },
    })
    await expect(fetchReport('datasets', 8, 'pdf')).rejects.toThrow('Reload the application')
    expect(isClientUpdateRequired()).toBe(true)
    expect(adapterMock.mock.calls[0][0].responseType).toBe('blob')
    await expect(fetchSelectedReport(7, 'excel')).rejects.toThrow('Reload the application')
    expect(adapterMock).toHaveBeenCalledOnce()
  })

  it('does not block on an ordinary 403 report-download Blob', async () => {
    adapterMock.mockRejectedValueOnce({
      response: {
        status: 403,
        data: new Blob([JSON.stringify({ code: 'permission_denied' })], { type: 'application/json' }),
      },
    })
    await expect(fetchSelectedReport(7, 'pdf')).rejects.toBeTruthy()
    expect(isClientUpdateRequired()).toBe(false)
    await fetchReport('datasets', 8, 'pdf')
    expect(adapterMock).toHaveBeenCalledTimes(2)
  })
})
