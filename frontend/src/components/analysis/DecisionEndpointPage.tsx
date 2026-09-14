import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { createWorkflowDecision, getWorkflow } from '../../api/workflow'
import { DecisionEndpoint } from '../decision/DecisionEndpoint'
import { ApiState } from '../ui/ApiState'

export function DecisionEndpointPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const queryClient = useQueryClient()
  const workflow = useQuery({
    queryKey: ['workflow', id],
    queryFn: () => getWorkflow(id),
    enabled: Number.isInteger(id),
  })
  const derive = useMutation({
    mutationFn: () => createWorkflowDecision(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workflow', id] })
    },
  })

  if (!Number.isInteger(id)) return <ApiState.ErrorState />
  if (workflow.isLoading) return <ApiState.Loading />
  if (workflow.isError || !workflow.data) return <ApiState.ErrorState />

  const decision = derive.data?.decision ?? workflow.data.decision?.result ?? null
  return (
    <DecisionEndpoint
      decision={decision}
      decisionStale={workflow.data.decision_stale}
      isPending={derive.isPending}
      error={derive.isError ? t('errors.server') : null}
      onDerive={() => derive.mutate()}
    />
  )
}
