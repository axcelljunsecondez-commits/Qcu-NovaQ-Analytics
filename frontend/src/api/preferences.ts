import { http } from '../lib/http'

// Optional preferences (spec 2026-10-09 B1). Saving never marks onboarding complete.
export interface Preferences {
  operation_type: string | null
  preferred_terminology: Record<string, string>
}

export async function getPreferences(): Promise<Preferences> {
  const { data } = await http.get<Preferences>('/account/preferences')
  return data
}

export async function savePreferences(preferences: Preferences): Promise<Preferences> {
  const { data } = await http.put<Preferences>('/account/preferences', preferences)
  return data
}
