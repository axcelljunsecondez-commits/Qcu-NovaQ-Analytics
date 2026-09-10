/**
 * DecisionEndpointPage - Wrapper that fetches analysis data and renders DecisionEndpoint.
 */
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { getAnalysis } from '../../api/analyses'
import { ApiState } from '../ui/ApiState'
import { DecisionEndpoint, getCompletionSteps } from '../decision/DecisionEndpoint'

export function DecisionEndpointPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)

  const analysis = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => getAnalysis(id),
    enabled: Number.isInteger(id),
  })

  if (!Number.isInteger(id)) return <ApiState.ErrorState />
  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState />

  const steps = getCompletionSteps(analysis.data.analysis, t)

  return <DecisionEndpoint steps={steps} analysisId={id} />
}
