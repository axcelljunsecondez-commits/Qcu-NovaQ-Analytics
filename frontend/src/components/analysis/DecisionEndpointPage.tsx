import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { getAnalysis } from '../../api/analyses'
import { createWorkflowDecision, getWorkflow, runSelectedDecision } from '../../api/workflow'
import { DecisionEndpoint } from '../decision/DecisionEndpoint'
import { ApiState } from '../ui/ApiState'
import { messageOf } from '../../lib/format'

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
  // Phase E: the method details read only the Many variations run this decision recorded as its evidence.
  const mc = workflow.data.mc
  const mcRows = decision?.evidence_ids?.mc != null && mc && decision.evidence_ids.mc === mc.id ? mc.result?.results ?? [] : []
  return (
    <DecisionEndpoint
      decision={decision}
      separate={isSeparate}
      decisionStale={workflow.data.decision_stale}
      isPending={derive.isPending}
      error={derive.isError ? messageOf(derive.error, t('errors.server')) : null}
      onDerive={() => derive.mutate()}
      mcRows={mcRows}
    />
  )
}
