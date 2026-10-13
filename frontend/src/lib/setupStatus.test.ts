import { describe, expect, it } from 'vitest'
import type { QueueSetup } from '../api/types'
import { missingSetupFields } from './setupStatus'

const complete: QueueSetup = {
  queue_structure: 'shared_queue', fixed_server_count: 3, staffing_varies_by_period: false, capacity_mode: 'unlimited',
  total_system_capacity: null, abandonment_mode: 'not_modeled', patience_rate_per_hour: null, segments: [],
  separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [],
}

describe('missingSetupFields (mirrors setup_status, U10 F4)', () => {
  it('finds nothing in a complete Setup', () => {
    expect(missingSetupFields(complete)).toEqual([])
    expect(missingSetupFields({ ...complete, fixed_server_count: null, staffing_varies_by_period: true })).toEqual([])
  })

  it('names each missing field with the input that sets it', () => {
    expect(missingSetupFields({ ...complete, fixed_server_count: null })).toEqual([{ field: 'fixed_server_count', inputId: 'server-count' }])
    expect(missingSetupFields({ ...complete, capacity_mode: 'finite' }).map((item) => item.inputId)).toEqual(['capacity-total'])
    expect(missingSetupFields({ ...complete, abandonment_mode: 'modeled' }).map((item) => item.inputId)).toEqual(['patience-rate'])
    expect(missingSetupFields({ ...complete, queue_structure: 'unknown' })).toEqual([{ field: 'queue_structure', inputId: null }])
  })
})
