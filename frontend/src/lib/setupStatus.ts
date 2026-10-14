import type { QueueSetup } from '../api/types'

/** A Setup field the server's `setup_status` needs, with the form field that sets it. */
export interface MissingSetupField {
  field: 'queue_structure' | 'total_system_capacity' | 'patience_rate_per_hour' | 'fixed_server_count'
  inputId: string | null
}

/**
 * What makes a Setup "incomplete", read field by field in the order of the server's rule
 * (`backend/api/analysis_schemas.py` `setup_status`). Shown only when the server says the Setup is incomplete;
 * it names the fields, it does not decide the status.
 */
export function missingSetupFields(setup: QueueSetup): MissingSetupField[] {
  const missing: MissingSetupField[] = []
  if (setup.queue_structure === 'unknown') missing.push({ field: 'queue_structure', inputId: null })
  if (setup.capacity_mode === 'finite' && setup.total_system_capacity == null) missing.push({ field: 'total_system_capacity', inputId: 'capacity-total' })
  if (setup.abandonment_mode === 'modeled' && setup.patience_rate_per_hour == null) missing.push({ field: 'patience_rate_per_hour', inputId: 'patience-rate' })
  if (!setup.staffing_varies_by_period && setup.fixed_server_count == null) missing.push({ field: 'fixed_server_count', inputId: 'server-count' })
  return missing
}
