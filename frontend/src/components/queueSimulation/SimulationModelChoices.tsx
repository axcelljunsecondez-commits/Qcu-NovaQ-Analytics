import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getAnalysis, patchAnalysis } from '../../api/analyses'
import type { QueueSetup } from '../../api/types'
import { requestError } from '../../lib/simulationEvidence'

type ModelChoices = Pick<QueueSetup, 'capacity_mode' | 'total_system_capacity' | 'abandonment_mode' | 'patience_rate_per_hour'>

function choicesOf(setup: QueueSetup): ModelChoices {
  return {
    capacity_mode: setup.capacity_mode, total_system_capacity: setup.total_system_capacity,
    abandonment_mode: setup.abandonment_mode, patience_rate_per_hour: setup.patience_rate_per_hour,
  }
}

export function SimulationModelChoices(props: {
  analysisId: number
  disabled: boolean
  focusRequest: number
  onPendingChange: (saving: boolean) => void
}) {
  return <ChoicesForAnalysis key={props.analysisId} {...props} />
}

function ChoicesForAnalysis({ analysisId, disabled, focusRequest, onPendingChange }: {
  analysisId: number
  disabled: boolean
  focusRequest: number
  onPendingChange: (saving: boolean) => void
}) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const analysis = useQuery({ queryKey: ['analysis', analysisId], queryFn: () => getAnalysis(analysisId) })
  const [draft, setDraft] = useState<ModelChoices | null>(null)
  const [saved, setSaved] = useState(false)
  const capacityFirst = useRef<HTMLInputElement>(null)
  const abandonmentFirst = useRef<HTMLInputElement>(null)
  const focusedRequest = useRef(0)
  const save = useMutation({
    mutationFn: async (choices: ModelChoices) => {
      // PATCH accepts a whole Setup: refresh first so unrelated staffing/break edits
      // made while this form was open are retained. The existing PATCH contract applies.
      const latest = await getAnalysis(analysisId)
      return patchAnalysis(analysisId, { queue_setup: { ...latest.analysis.queue_setup, ...choices } })
    },
    onSuccess: async (result) => {
      client.setQueryData(['analysis', analysisId], result)
      setDraft(null); setSaved(true)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['analyses'] }),
        client.invalidateQueries({ queryKey: ['current', analysisId] }),
        client.resetQueries({ queryKey: ['workflow', analysisId] }),
        client.resetQueries({ queryKey: ['scenarios', analysisId] }),
        client.invalidateQueries({ queryKey: ['continuous-compat', analysisId] }),
        client.invalidateQueries({ queryKey: ['continuous-runs', analysisId] }),
        client.invalidateQueries({ queryKey: ['continuous-run', analysisId] }),
      ])
    },
  })
  // A run must use persisted choices. Keep it blocked until a draft is saved or cancelled.
  useEffect(() => onPendingChange(Boolean(draft) || save.isPending), [draft, save.isPending, onPendingChange])
  useEffect(() => () => onPendingChange(false), [onPendingChange])
  const setup = analysis.data?.analysis.queue_setup
  useEffect(() => {
    if (!focusRequest || !setup || focusedRequest.current === focusRequest) return
    focusedRequest.current = focusRequest
    const target = setup.capacity_mode === 'unknown' ? capacityFirst : abandonmentFirst
    target.current?.focus()
  }, [focusRequest, setup])

  if (!setup && analysis.isPending) return <p role="status">{t('common.loading')}</p>
  if (!setup || analysis.isError) return <div role="alert" className="alert alert-error">
    {requestError(analysis.error, t('errors.server'))}
  </div>
  if (setup.queue_structure !== 'shared_queue') return null
  const choices = draft ?? choicesOf(setup)
  const valid = (choices.capacity_mode !== 'finite' || (Number.isInteger(choices.total_system_capacity)
    && (choices.total_system_capacity ?? 0) >= 1 && (choices.total_system_capacity ?? 0) <= 100000))
    && (choices.abandonment_mode !== 'modeled' || (Number.isFinite(choices.patience_rate_per_hour)
      && (choices.patience_rate_per_hour ?? 0) > 0))
  const update = (next: ModelChoices) => { setDraft(next); setSaved(false); save.reset() }
  return (
    <form className="simulation-model-choices" onSubmit={(event) => {
      event.preventDefault()
      if (!draft || !valid || disabled || save.isPending || analysis.data?.analysis.archived_at) return
      save.mutate(draft)
    }}>
      <fieldset disabled={disabled || save.isPending || Boolean(analysis.data?.analysis.archived_at)} aria-label={t('analyses.queue_setup')}>
        <fieldset className="form-field">
          <legend>{t('setup.capacity')}</legend>
          {(['unlimited', 'finite', 'unknown'] as const).map((mode, index) => <label key={mode} className="radio-row">
            <input ref={index === 0 ? capacityFirst : undefined} type="radio" name={`simulation-capacity-${analysisId}`}
              checked={choices.capacity_mode === mode} onChange={() => update({ ...choices, capacity_mode: mode,
                total_system_capacity: mode === 'finite' ? choices.total_system_capacity : null })} />
            {t(mode === 'unknown' ? 'setup.capacity_not_sure' : `setup.capacity_${mode}`)}
          </label>)}
          {choices.capacity_mode === 'finite' && <div className="form-field">
            <label htmlFor={`simulation-capacity-total-${analysisId}`}>{t('analyses.total_capacity')}</label>
            <input id={`simulation-capacity-total-${analysisId}`} type="number" min={1} max={100000} step={1} required
              value={choices.total_system_capacity ?? ''} onChange={(event) => update({ ...choices,
                total_system_capacity: event.target.value === '' ? null : Number(event.target.value) })} />
          </div>}
        </fieldset>
        <fieldset className="form-field">
          <legend>{t('setup.abandonment')}</legend>
          {(['not_modeled', 'modeled', 'unknown'] as const).map((mode, index) => <label key={mode} className="radio-row">
            <input ref={index === 0 ? abandonmentFirst : undefined} type="radio" name={`simulation-abandonment-${analysisId}`}
              checked={choices.abandonment_mode === mode} onChange={() => update({ ...choices, abandonment_mode: mode,
                patience_rate_per_hour: mode === 'modeled' ? choices.patience_rate_per_hour : null })} />
            {t(mode === 'unknown' ? 'setup.abandonment_not_sure' : mode === 'modeled' ? 'setup.abandonment_yes' : 'setup.abandonment_no')}
          </label>)}
          {choices.abandonment_mode === 'modeled' && <div className="form-field">
            <label htmlFor={`simulation-patience-${analysisId}`}>{t('analyses.theta')}</label>
            <input id={`simulation-patience-${analysisId}`} type="number" min={0} step="any" required
              value={choices.patience_rate_per_hour ?? ''} onChange={(event) => update({ ...choices,
                patience_rate_per_hour: event.target.value === '' ? null : Number(event.target.value) })} />
            <span className="form-hint">{t('analyses.theta_required')}</span>
          </div>}
        </fieldset>
        {(choices.capacity_mode === 'unknown' || choices.abandonment_mode === 'unknown')
          && <p className="form-hint">{t('setup.read_not_sure_note')}</p>}
        {(choices.capacity_mode === 'finite' || choices.abandonment_mode === 'modeled')
          && <p className="form-hint">{t('continuous.reason.capacity_or_abandonment')}</p>}
        <div className="button-row">
          <button type="submit" disabled={!draft || !valid || disabled || save.isPending}>{t(save.isPending ? 'common.saving' : 'common.save')}</button>
          {draft && <button type="button" className="btn-ghost" disabled={save.isPending} onClick={() => { setDraft(null); save.reset() }}>{t('common.cancel')}</button>}
        </div>
      </fieldset>
      {saved && <p role="status">{t('analyses.setup_saved')}</p>}
      {save.isError && <div role="alert" className="alert alert-error">{requestError(save.error, t('errors.server'))}</div>}
    </form>
  )
}
