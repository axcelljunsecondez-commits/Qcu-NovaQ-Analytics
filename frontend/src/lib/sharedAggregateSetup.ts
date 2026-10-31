import type { SharedAggregateChoices, SharedAggregatePreviewOut } from '../api/types'

/** Upload defers missing operational answers; it never substitutes supported assumptions. */
export function deferredSharedChoices(preview: SharedAggregatePreviewOut): SharedAggregateChoices {
  return Object.fromEntries(preview.unresolved.map((field) => [field, 'unknown']))
}

/** Only explicit missing answers and valid required numbers enable the shared-file apply action. */
export function sharedChoicesComplete(preview: SharedAggregatePreviewOut, choices: SharedAggregateChoices): boolean {
  if (preview.unresolved.some((field) => choices[field] === undefined)) return false
  const capacity = preview.unresolved.includes('capacity_mode') ? choices.capacity_mode : preview.saved_setup.capacity_mode
  const total = preview.unresolved.includes('capacity_mode') ? choices.total_system_capacity : preview.saved_setup.total_system_capacity
  const abandonment = preview.unresolved.includes('abandonment_mode') ? choices.abandonment_mode : preview.saved_setup.abandonment_mode
  const patience = preview.unresolved.includes('abandonment_mode') ? choices.patience_rate_per_hour : preview.saved_setup.patience_rate_per_hour
  if (capacity === 'finite' && (!Number.isInteger(total) || (total ?? 0) < 1 || (total ?? 0) > 100000)) return false
  if (abandonment === 'modeled' && (!Number.isFinite(patience) || (patience ?? 0) <= 0)) return false
  return true
}
