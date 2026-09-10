/**
 * Onboarding API client for NovaQ frontend.
 */

import { http } from '../lib/http'

export interface OnboardingStatus {
  completed: boolean
  operation_type: string | null
  preferred_terminology: Record<string, string>
}

export interface OnboardingCompleteRequest {
  operation_type: string
  preferred_terminology: Record<string, string>
}

export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  const response = await http.get('/onboarding/status')
  return response.data
}

export async function completeOnboarding(
  data: OnboardingCompleteRequest,
): Promise<OnboardingStatus> {
  const response = await http.post('/onboarding/complete', data)
  return response.data
}
