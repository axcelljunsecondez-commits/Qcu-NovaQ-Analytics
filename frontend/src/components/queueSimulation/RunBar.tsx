import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getAnalysisCurrent } from '../../api/analyses'
import { runSelectedDes, runWorkflowDes, runWorkflowDesCurrent } from '../../api/workflow'
import { parseSeed, requestError } from '../../lib/simulationEvidence'
import { operatingHours } from '../../lib/replay'
import { breakNoticeKey, currentRun, runBasisKey, suggestedRun, type RunChoice, type SimulationContext } from './simulationContext'

/** One-row run bar (D30): hours, closing rule, status, Run full operation, Advanced. */
export function RunBar({ context, run, runLabelKey = 'simulation.run_full_operation' }: { context: SimulationContext; run: RunChoice; runLabelKey?: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { analysisId } = context
  const [seed, setSeed] = useState(run === 'suggested' && context.selectedSeparate ? '42' : '')
  const [hours, setHours] = useState('24')
  const [overload, setOverload] = useState('20')
  const [maxEvents, setMaxEvents] = useState('3000')
  const [error, setError] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
  const legacyOptions = () => ({
    sim_hours: Number(hours), queue_overload_threshold: Number(overload), max_events: Number(maxEvents), seed: parseSeed(seed), carryover: true,
  })
  const runMutation = useMutation({
    mutationFn: async () => {
      if (run === 'current') return runWorkflowDesCurrent(analysisId, legacyOptions())
      if (context.selectedSeparate) return runSelectedDes(analysisId, { seed: parseSeed(seed) })
      return runWorkflowDes(analysisId, legacyOptions())
    },
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const stored = run === 'current' ? currentRun(context) : suggestedRun(context)?.result ?? null
  // D7: name the dataset Current would run on only from a settled server lookup.
  const currentDataset = useQuery({
    queryKey: ['current', analysisId],
    queryFn: () => getAnalysisCurrent(analysisId),
    enabled: run === 'current' && stored === null,
    retry: false,
    staleTime: 0,
  })
  const lookedUp = currentDataset.isSuccess && !currentDataset.isFetching ? currentDataset.data.dataset.id : undefined
  const legacy = run === 'current' || !context.selectedSeparate
  const canRun = run === 'current' || context.scenario !== null
  const usedSeed = run === 'current' ? context.workflow.des_current?.params.seed : context.workflow.des?.params.seed
  // A run whose periods could not be simulated is not kept as evidence; say why instead of "Not run".
  const returnedRows = ((runMutation.data?.evidence.result as { results?: Array<{ time?: unknown; error?: unknown; simulation_supported?: unknown }> } | undefined)?.results) ?? []
  const capabilityErrors = [...new Set(returnedRows.filter((row) => row.simulation_supported === false && typeof row.error === 'string')
    .map((row) => `${String(row.time)}: ${String(row.error)}`))]
  const hoursText = operatingHours(context.analysis.queue_setup)

  function start() {
    if (legacy) {
      const simHours = Number(hours)
      const threshold = Number(overload)
      const events = Number(maxEvents)
      if (!Number.isFinite(simHours) || simHours <= 0 || simHours > 168) return setError(t('simulation.hours_range_error'))
      if (!Number.isInteger(threshold) || threshold < 1) return setError(t('simulation.overload_range_error'))
      if (!Number.isInteger(events) || events < 1 || events > 3000) return setError(t('simulation.workflow_events_range_error'))
    }
    setError(null)
    runMutation.mutate()
  }

  return (
    <section className="card run-bar" aria-label={t('simulation.run_bar')}>
      <div className="run-bar-row">
        <span>{hoursText ? t('simulation.operating_hours', { hours: hoursText }) : t('simulation.operating_hours_unknown')}</span>
        {context.separate && <span>{t('simulation.closing_rule_separate')}</span>}
        <span className={`badge ${runMutation.isPending ? 'badge-warn' : stored ? 'badge-ok' : 'badge-neutral'}`} role="status" data-testid="run-status">
          {t(runMutation.isPending ? 'simulation.status_running' : stored ? 'simulation.status_done' : 'simulation.status_not_run')}
        </span>
        <button type="button" className="btn-primary" onClick={start} disabled={!canRun || runMutation.isPending}>
          {runMutation.isPending ? t('common.loading') : t(runLabelKey)}
        </button>
      </div>
      <p className="form-hint">
        {t(runBasisKey(context, run))}
        {stored && typeof usedSeed === 'number' && ` · ${t('simulation.run_seed', { seed: usedSeed })}`}
        {run === 'current' && stored && <> · <span className="badge badge-ok">{t('simulation.current_badge')}</span></>}
      </p>
      {breakNoticeKey(context, run) && (
        <p role="note" className="alert alert-warn" data-testid="break-notice">{t(breakNoticeKey(context, run) as string)}</p>
      )}
      {run === 'current' && stored === null && lookedUp !== undefined && (
        <p role="status" className="form-hint">{t('simulation.no_current_run', { dataset: lookedUp })}</p>
      )}
      <details className="run-advanced">
        <summary>{t('simulation.advanced')}</summary>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="run-seed">{t('simulation.seed')}</label>
            <input id="run-seed" type="number" step={1} value={seed} onChange={(event) => setSeed(event.target.value)} />
            <span className="form-hint">{t(legacy ? 'simulation.seed_default_random' : 'simulation.seed_default', { seed: 42 })}</span>
          </div>
          {legacy && (
            <>
              <div className="form-field">
                <label htmlFor="run-hours">{t('simulation.hours')}</label>
                <input id="run-hours" type="number" value={hours} onChange={(event) => setHours(event.target.value)} />
                <span className="form-hint">{t('simulation.default_value', { value: 24 })}</span>
              </div>
              <div className="form-field">
                <label htmlFor="run-overload">{t('simulation.overload')}</label>
                <input id="run-overload" type="number" value={overload} onChange={(event) => setOverload(event.target.value)} />
                <span className="form-hint">{t('simulation.default_value', { value: 20 })}</span>
              </div>
              <div className="form-field">
                <label htmlFor="run-events">{t('simulation.live_max_events')}</label>
                <input id="run-events" type="number" value={maxEvents} onChange={(event) => setMaxEvents(event.target.value)} />
                <span className="form-hint">{t('simulation.default_value', { value: 3000 })}</span>
              </div>
            </>
          )}
        </div>
      </details>
      {error && <div role="alert" className="alert alert-error">{error}</div>}
      {capabilityErrors.length > 0 && (
        <div role="alert" className="alert alert-warn" data-testid="run-capability-errors">
          <strong>{t(capabilityErrors.length === returnedRows.length ? 'simulation.run_unsupported_all' : 'simulation.run_unsupported_some')}</strong>
          <ul>{capabilityErrors.map((line) => <li key={line}>{line}</li>)}</ul>
        </div>
      )}
    </section>
  )
}
