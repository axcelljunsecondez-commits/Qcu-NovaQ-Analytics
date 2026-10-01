import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http } from '../lib/http'
import {
  createNamedRun,
  getNamedContract,
  getNamedReplication,
  getNamedRun,
  listNamedRuns,
  namedApiError,
  validateNamedInputs,
  type NamedRunRequest,
} from './sharedNamed'
import fixture from '../test/fixtures/sharedNamed.json'

interface Captured { method?: string; url?: string; data?: string; headers: Record<string, string> }

const adapterMock = vi.fn(async (config: Captured) => ({
  data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config,
}))

beforeEach(() => {
  adapterMock.mockClear()
  http.defaults.adapter = adapterMock as never
  document.cookie = 'novaq_csrf=named-token'
})

afterEach(() => {
  document.cookie = 'novaq_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

const request = fixture.request as unknown as NamedRunRequest

describe('sharedNamed client', () => {
  it('uses the exact method and URL for each route', async () => {
    await getNamedContract(7)
    await listNamedRuns(7)
    await getNamedRun(7, 3)
    await getNamedReplication(7, 3, 2)
    const calls = adapterMock.mock.calls.map(([config]) => [config.method, config.url])
    expect(calls).toEqual([
      ['get', '/analyses/7/shared-named/contract'],
      ['get', '/analyses/7/shared-named/runs'],
      ['get', '/analyses/7/shared-named/runs/3'],
      ['get', '/analyses/7/shared-named/runs/3/replications/2'],
    ])
    for (const [config] of adapterMock.mock.calls) expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('posts the body unchanged and relies on the CSRF interceptor', async () => {
    const { replications, seed, ...workforce } = request
    await validateNamedInputs(7, workforce)
    await createNamedRun(7, { ...workforce, replications, seed })
    const [[validate], [run]] = adapterMock.mock.calls
    expect([validate.method, validate.url]).toEqual(['post', '/analyses/7/shared-named/validate'])
    expect(JSON.parse(validate.data ?? '')).toEqual(workforce)
    expect([run.method, run.url]).toEqual(['post', '/analyses/7/shared-named/runs'])
    expect(JSON.parse(run.data ?? '')).toEqual(request)
    expect(validate.headers['X-CSRF-Token']).toBe('named-token')
    expect(run.headers['X-CSRF-Token']).toBe('named-token')
  })

  it('keeps null pay values as null in the sent body', async () => {
    await createNamedRun(7, request)
    const sent = JSON.parse(adapterMock.mock.calls[0][0].data ?? '') as NamedRunRequest
    expect(sent.employees[1].pay).toEqual({ regular_rate_per_hour: null, overtime_rate_per_hour: null, daily_regular_paid_minutes: null })
  })
})

describe('namedApiError', () => {
  it('reads the structured code and status', () => {
    const error = { response: { status: 422, data: { detail: { code: 'persistence_identity_mismatch', checks: [] } } } }
    expect(namedApiError(error)).toEqual({ status: 422, code: 'persistence_identity_mismatch', detail: { code: 'persistence_identity_mismatch', checks: [] } })
  })

  it('never invents a code for a validation list or a plain string', () => {
    expect(namedApiError({ response: { status: 422, data: { detail: [{ loc: ['body'] }] } } }).code).toBeNull()
    expect(namedApiError({ response: { status: 401, data: { detail: 'Not authenticated.' } } }).code).toBeNull()
    expect(namedApiError(new Error('network')).status).toBeNull()
  })
})
