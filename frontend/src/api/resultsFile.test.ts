import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http } from '../lib/http'
import { getAnalysisCurrent } from './analyses'
import { getObservedWait } from './workflow'

interface Captured { method?: string; url?: string; params?: Record<string, unknown> }

const adapterMock = vi.fn(async (config: Captured) => ({
  data: {}, status: 200, statusText: 'OK', headers: {}, config,
}))

beforeEach(() => {
  adapterMock.mockClear()
  http.defaults.adapter = adapterMock as never
})

describe('results for any processed file (B3)', () => {
  it('asks for the planning file when no file is named', async () => {
    await getAnalysisCurrent(7)
    await getObservedWait(7)
    const calls = adapterMock.mock.calls.map(([config]) => [config.url, config.params])
    expect(calls).toEqual([['/analyses/7/current', undefined], ['/analyses/7/workflow/observed-wait', undefined]])
  })

  it('names the chosen file as dataset_id', async () => {
    await getAnalysisCurrent(7, 12)
    await getObservedWait(7, 12)
    const calls = adapterMock.mock.calls.map(([config]) => [config.url, config.params])
    expect(calls).toEqual([
      ['/analyses/7/current', { dataset_id: 12 }],
      ['/analyses/7/workflow/observed-wait', { dataset_id: 12 }],
    ])
  })
})
