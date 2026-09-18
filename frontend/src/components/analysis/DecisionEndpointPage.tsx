import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { getAnalysis } from '../../api/analyses'
import { createWorkflowDecision, getWorkflow, runSelectedDecision } from '../../api/workflow'
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
  const analysis = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => getAnalysis(id),
    enabled: Number.isInteger(id),
  })
  const isSeparate = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'
  const derive = useMutation({
    // Separate plans are decided by the selected-plan endpoint; the persisted
    // result is then read back through the workflow query.
    mutationFn: async () => {
      if (isSeparate) {
        await runSelectedDecision(id)
        return null
      }
      return (await createWorkflowDecision(id)).decision
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workflow', id] })
    },
  })

  if (!Number.isInteger(id)) return <ApiState.ErrorState />
  if (workflow.isLoading || analysis.isLoading) return <ApiState.Loading />
  if (workflow.isError || !workflow.data || analysis.isError) return <ApiState.ErrorState />

  const decision = derive.data ?? workflow.data.decision?.result ?? null
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
