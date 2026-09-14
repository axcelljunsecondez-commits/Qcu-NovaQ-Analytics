import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getOnboardingStatus } from '../api/onboarding'
import { ApiState } from '../components/ui/ApiState'

export function RequireOnboarding() {
  const location = useLocation()
  const status = useQuery({
    queryKey: ['onboarding'],
    queryFn: getOnboardingStatus,
  })

  if (status.isLoading) return <ApiState.Loading />
  if (status.isError || !status.data) return <ApiState.ErrorState error={status.error} />

  if (!status.data.completed) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/onboarding" replace state={{ from }} />
  }

  return <Outlet />
}
