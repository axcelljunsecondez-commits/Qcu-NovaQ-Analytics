import simulationDefaults from '../api/simulation-defaults.json'
import { useRef, useState, type KeyboardEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { SimDesOut, SimMcOut, SimValidateOut } from '../api/types'
import {
  getWorkflow,
  runWorkflowDes,
  runWorkflowDesCurrent,
  runWorkflowMc,
  runWorkflowMcCurrent,
  runWorkflowValidation,
  runWorkflowValidationCurrent,
} from '../api/workflow'
import { getAnalysis } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'
import { MetricCard } from '../components/ui/MetricCard'
import { LiveSimulationPlayback } from '../components/simulation/LiveSimulationPlayback'
import { SeparateSimulationPlayback } from '../components/simulation/SeparateSimulationPlayback'
import { selectPlaybackLayout } from '../lib/simulationPlayback'
import {
  FailureRateBars,
  LqHistogram,
  MaxQueueBars,
  RhoLqLines,
  RhoMeanP95Lines,
  UtilizationHeatmap,
} from '../components/charts/Charts'
import { downloadCsv, fmt, fmtFrCi, fmtPct } from '../lib/format'

type Tab = 'des' | 'mc' | 'validate'

const TABS: Array<{ id: Tab; labelKey: string }> = [
  { id: 'des', labelKey: 'simulation.tabs.des_live' },
  { id: 'mc', labelKey: 'simulation.tabs.mc' },
  { id: 'validate', labelKey: 'simulation.tabs.validate' },
]

const MC_MAX_TRIALS = 100000

function parseSeed(raw: string): number | null {
  if (!raw.trim()) return null
  const value = Number(raw)
  return Number.isInteger(value) ? value : null
}

function requestError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } })
    .response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

function validProbability(value: number): boolean {
  return Number.isFinite(value) && value > 0 && value <= 1
}

function validationPasses(row: SimValidateOut, cap: number): boolean {
  return (
    row.simulation_supported !== false
    && !row.validation_reason
    && !['ERROR', 'Critical', 'Unstable'].includes(row.sim_status)
    && Number.isFinite(row.mc_failure_rate)
    && row.mc_failure_rate <= cap
    && row.mc_failure_rate_adequate === true
  )
}

function storedNumberDiffers(raw: string, stored: unknown): boolean {
  return typeof stored === 'number' && Number.isFinite(stored) && Number(raw) !== stored
}

function storedSeedDiffers(raw: string, stored: unknown): boolean {
  if (stored === null) return parseSeed(raw) !== null
  return typeof stored === 'number' && Number.isFinite(stored) && parseSeed(raw) !== stored
}

function PrecisionBadge({ level }: { level: SimMcOut['failure_rate_precision'] }) {
  if (!level) return <span className="badge badge-neutral">—</span>
  const style = level === 'high' ? 'badge-ok' : level === 'moderate' ? 'badge-warn' : 'badge-bad'
  return <span className={`badge ${style}`}>{level}</span>
}

export function SimulationPage() {
  const { t } = useTranslation()
  const analysisId = Number(useParams().analysisId)
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('des')
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ des: null, mc: null, validate: null })
  const [error, setError] = useState<string | null>(null)
  const [desHours, setDesHours] = useState('24')
  const [desThreshold, setDesThreshold] = useState('20')
  const [maxEvents, setMaxEvents] = useState('3000')
  const [desSeed, setDesSeed] = useState('')
  const [mcTrials, setMcTrials] = useState(String(simulationDefaults.num_trials))
  const [mcThreshold, setMcThreshold] = useState(String(simulationDefaults.failure_threshold))
  const [failureCap, setFailureCap] = useState(String(simulationDefaults.failure_rate_cap))
  const [mcSeed, setMcSeed] = useState('')
  const [validationTrials, setValidationTrials] = useState('10000')
  const [validationHours, setValidationHours] = useState('24')
  const [validationSeed, setValidationSeed] = useState('')

  const workflow = useQuery({
    queryKey: ['workflow', analysisId],
    queryFn: () => getWorkflow(analysisId),
    enabled: Number.isInteger(analysisId),
  })
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => getAnalysis(analysisId),
    enabled: Number.isInteger(analysisId),
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
  const desRun = useMutation({
    mutationFn: () => runWorkflowDes(analysisId, {
      sim_hours: Number(desHours),
      queue_overload_threshold: Number(desThreshold),
      max_events: Number(maxEvents),
      seed: parseSeed(desSeed),
      carryover: true,
    }),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const mcRun = useMutation({
    mutationFn: () => runWorkflowMc(analysisId, {
      num_trials: Number(mcTrials),
      failure_threshold: Number(mcThreshold),
      failure_rate_cap: Number(failureCap),
      seed: parseSeed(mcSeed),
    }),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const mcCurrentRun = useMutation({
    mutationFn: () => runWorkflowMcCurrent(analysisId, {
      num_trials: Number(mcTrials),
      failure_threshold: Number(mcThreshold),
      failure_rate_cap: Number(failureCap),
      seed: parseSeed(mcSeed),
    }),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const desCurrentRun = useMutation({
    mutationFn: () => runWorkflowDesCurrent(analysisId, {
      sim_hours: Number(desHours),
      queue_overload_threshold: Number(desThreshold),
      max_events: Number(maxEvents),
      seed: parseSeed(desSeed),
      carryover: true,
    }),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const validationRun = useMutation({
    mutationFn: () => runWorkflowValidation(analysisId, {
      des_sim_hours: Number(validationHours),
      mc_trials: Number(validationTrials),
      mc_failure_threshold: Number(mcThreshold),
      mc_failure_rate_cap: Number(failureCap),
      seed: parseSeed(validationSeed),
    }),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })
  const validationCurrentRun = useMutation({
    mutationFn: () => runWorkflowValidationCurrent(analysisId),
    onSuccess: refresh,
    onError: (err) => setError(requestError(err, t('errors.server'))),
  })

  if (!Number.isInteger(analysisId)) return <ApiState.ErrorState />
  if (workflow.isLoading || analysis.isLoading) return <ApiState.Loading />
  if (workflow.isError || !workflow.data) return <ApiState.ErrorState />

  const scenario = workflow.data.scenario
  const queueStructure = analysis.data?.analysis.queue_setup.queue_structure
  const isCurrentMode = !scenario && queueStructure === 'separate_queues'
  if (!scenario && !isCurrentMode) {
    return (
      <div>
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">{t('simulation.workflow_eyebrow')}</div>
            <h1 className="page-title">{t('simulation.title')}</h1>
          </div>
        </div>
        <div className="alert alert-warn">
          {t('simulation.select_scenario_first')}{' '}
          <Link to={`/analyses/${analysisId}/compare`}>{t('nav.compare')}</Link>
        </div>
      </div>
    )
  }

  const trace = isCurrentMode
    ? desCurrentRun.data?.evidence.result ?? workflow.data.des_current?.result ?? null
    : desRun.data?.evidence.result ?? workflow.data.des?.result ?? null
  const desRows: SimDesOut[] = trace?.results ?? []
  const activePlaybackSegment = trace?.segments.find(
    (item) => item.simulation_supported && !item.error,
  ) ?? trace?.segments[0] ?? null
  const playbackLayout = activePlaybackSegment
    ? selectPlaybackLayout(activePlaybackSegment.queue_structure)
    : 'shared'
  const mcRows = isCurrentMode
    ? mcCurrentRun.data?.evidence.result.results ?? workflow.data.mc_current?.result.results ?? []
    : mcRun.data?.evidence.result.results ?? workflow.data.mc?.result.results ?? []
  const showMcQueueColumn = mcRows.some((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  const validationEvidence = validationRun.data?.evidence ?? workflow.data.validation
  const validationRows = validationEvidence?.result.results ?? []
  const validationCurrent = validationCurrentRun.data?.evidence ?? workflow.data.validation_current
  const validationCurrentRows = validationCurrent?.result.results ?? []
  const validationCurrentVerdict = validationCurrent?.result.verdict ?? null
  const hasMcCurrent = (workflow.data.mc_current?.result.results ?? []).length > 0
    || (mcCurrentRun.data?.evidence.result.results ?? []).length > 0
  const cap = Number(failureCap)
  const savedCapValue = validationEvidence?.params.mc_failure_rate_cap
  const savedFailureCap = typeof savedCapValue === 'number' && validProbability(savedCapValue)
    ? savedCapValue
    : null
  const validationSettingsChanged = Boolean(validationEvidence) && (
    storedNumberDiffers(validationHours, validationEvidence?.params.des_sim_hours)
    || storedNumberDiffers(validationTrials, validationEvidence?.params.mc_trials)
    || storedNumberDiffers(mcThreshold, validationEvidence?.params.mc_failure_threshold)
    || storedNumberDiffers(failureCap, validationEvidence?.params.mc_failure_rate_cap)
    || storedSeedDiffers(validationSeed, validationEvidence?.params.seed)
  )
  const validationPassed = savedFailureCap !== null
    && validationRows.length > 0
    && validationRows.every((row) => validationPasses(row, savedFailureCap))
  const running = desRun.isPending || desCurrentRun.isPending || mcRun.isPending || mcCurrentRun.isPending || validationRun.isPending || validationCurrentRun.isPending

  function begin(tabId: Tab) {
    setTab(tabId)
    setError(null)
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % TABS.length
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + TABS.length) % TABS.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = TABS.length - 1
    if (nextIndex === null) return
    event.preventDefault()
    const next = TABS[nextIndex].id
    begin(next)
    tabRefs.current[next]?.focus()
  }

  function submitDes() {
    const hours = Number(desHours)
    const threshold = Number(desThreshold)
    const events = Number(maxEvents)
    if (!Number.isFinite(hours) || hours <= 0 || hours > 168) {
      setError(t('simulation.hours_range_error'))
    } else if (!Number.isInteger(threshold) || threshold < 1) {
      setError(t('simulation.overload_range_error'))
    } else if (!Number.isInteger(events) || events < 1 || events > 3000) {
      setError(t('simulation.workflow_events_range_error'))
    } else {
      setError(null)
      if (isCurrentMode) desCurrentRun.mutate()
      else desRun.mutate()
    }
  }

  function submitMc() {
    const trials = Number(mcTrials)
    const threshold = Number(mcThreshold)
    if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) {
      setError(t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) }))
    } else if (!validProbability(threshold)) {
      setError(t('simulation.threshold_range_error'))
    } else if (!validProbability(cap)) {
      setError(t('simulation.cap_range_error'))
    } else {
      setError(null)
      if (isCurrentMode) mcCurrentRun.mutate()
      else mcRun.mutate()
    }
  }

  function submitValidation() {
    const trials = Number(validationTrials)
    const hours = Number(validationHours)
    if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) {
      setError(t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) }))
    } else if (!Number.isFinite(hours) || hours <= 0 || hours > 168) {
      setError(t('simulation.hours_range_error'))
    } else if (!validProbability(Number(mcThreshold))) {
      setError(t('simulation.threshold_range_error'))
    } else if (!validProbability(cap)) {
      setError(t('simulation.cap_range_error'))
    } else {
      setError(null)
      validationRun.mutate()
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t(isCurrentMode ? 'simulation.current_mode_eyebrow' : 'simulation.workflow_eyebrow')}</div>
          <h1 className="page-title">{t(isCurrentMode ? 'simulation.simulate_current_title' : 'simulation.title')}</h1>
          <p className="page-caption">
            {isCurrentMode
              ? t('simulation.current_mode_help')
              : t('simulation.selected_scenario', { name: scenario?.name ?? '' })}
          </p>
        </div>
      </div>
      {isCurrentMode && trace && (
        <p className="form-hint">
          <span className="badge badge-ok">{t('simulation.current_badge')}</span>
        </p>
      )}
      <p className="form-hint">{t('integrity.simulation_coverage')}</p>
      {error && <div role="alert" className="alert alert-error">{error}</div>}

      {!isCurrentMode && (
      <div className="tab-bar" role="tablist">
        {TABS.map((item, index) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`simulation-tab-${item.id}`}
            aria-controls={`simulation-panel-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            ref={(node) => { tabRefs.current[item.id] = node }}
            className={tab === item.id ? 'active' : ''}
            onClick={() => begin(item.id)}
            onKeyDown={(event) => handleTabKey(event, index)}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      )}

      {(tab === 'des' || isCurrentMode) && (
        <section id="simulation-panel-des" role="tabpanel" aria-labelledby="simulation-tab-des" tabIndex={0}>
          <div className="card simulation-controls">
            <h3 className="section-title">{t('simulation.unified_des_title')}</h3>
            <p className="form-hint">{t('simulation.unified_des_help')}</p>
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="des-hours">{t('simulation.hours')}</label>
                <input id="des-hours" type="number" value={desHours} onChange={(e) => setDesHours(e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="des-threshold">{t('simulation.overload')}</label>
                <input id="des-threshold" type="number" value={desThreshold} onChange={(e) => setDesThreshold(e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="des-events">{t('simulation.live_max_events')}</label>
                <input id="des-events" type="number" value={maxEvents} onChange={(e) => setMaxEvents(e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="des-seed">{t('simulation.seed')}</label>
                <input id="des-seed" type="number" value={desSeed} onChange={(e) => setDesSeed(e.target.value)} />
              </div>
              <button type="button" className="btn-primary" disabled={running} onClick={submitDes}>
                {running ? t('common.loading') : t(isCurrentMode ? 'simulation.run_current_des' : 'simulation.run_unified_des')}
              </button>
            </div>
          </div>
          {trace && (
            <>
              <div className="card-grid">
                <MetricCard label={t('simulation.stable')} value={desRows.filter((row) => ['Lean', 'Normal', 'Peak'].includes(row.status)).length} />
                <MetricCard label={t('simulation.critical')} value={desRows.filter((row) => ['Critical', 'Unstable', 'ERROR'].includes(row.status)).length} />
                <MetricCard label={t('simulation.served')} value={desRows.reduce((sum, row) => sum + row.served, 0)} />
                <MetricCard label={t('simulation.live_complete')} value={trace.event_count} />
              </div>
              <p className="form-hint">
                <span className="badge badge-neutral">
                  {t(playbackLayout === 'separate'
                    ? 'simulation.playback_view_separate'
                    : 'simulation.playback_view_shared')}
                </span>
              </p>
              {playbackLayout === 'separate'
                ? <SeparateSimulationPlayback trace={trace} />
                : <LiveSimulationPlayback trace={trace} />}
              <div className="card table-scroll" role="region" aria-label={t('simulation.des_table_caption')} tabIndex={0}>
                <table>
                  <caption className="sr-only">{t('simulation.des_table_caption')}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{t('common.time')}</th>
                      <th scope="col">{t('simulation.status')}</th>
                      <th scope="col">ρ</th>
                      <th scope="col">Lq</th>
                      <th scope="col">{t('system.sim_wait_minutes')}</th>
                      <th scope="col">{t('simulation.max_queue')}</th>
                      <th scope="col">{t('simulation.served')}</th>
                      <th scope="col">{t('simulation.dropped')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {desRows.map((row) => (
                      <tr key={row.time}>
                        <th scope="row">{row.time}</th>
                        <td>{row.status}</td>
                        <td>{fmt(row.rho_sim, 3)}</td>
                        <td>{fmt(row.Lq_sim, 3)}</td>
                        <td>{fmt(row.Wq_sim == null ? null : row.Wq_sim * 60, 2)}</td>
                        <td>{row.max_queue}</td>
                        <td>{row.served}</td>
                        <td>{row.dropped}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card-grid">
                <div className="card"><UtilizationHeatmap rows={desRows} /></div>
                <div className="card"><RhoLqLines rows={desRows} /></div>
                <div className="card"><MaxQueueBars rows={desRows} /></div>
                <div className="card"><LqHistogram rows={desRows} /></div>
              </div>
              <button type="button" className="btn-ghost" onClick={() => downloadCsv('novaq_unified_des.csv', desRows as unknown as Record<string, unknown>[])}>
                {t('simulation.download_csv')}
              </button>
            </>
          )}
        </section>
      )}

      {((!isCurrentMode && tab === 'mc') || isCurrentMode) && (
        <section id="simulation-panel-mc" role="tabpanel" aria-labelledby="simulation-tab-mc" tabIndex={0}>
          <div className="card simulation-controls">
            <h3 className="section-title">{t('simulation.tabs.mc')}</h3>
            <div className="form-row">
              <div className="form-field"><label htmlFor="mc-trials">{t('simulation.trials')}</label><input id="mc-trials" type="number" value={mcTrials} onChange={(e) => setMcTrials(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="mc-threshold">{t('simulation.threshold')}</label><input id="mc-threshold" type="number" step="any" value={mcThreshold} onChange={(e) => setMcThreshold(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="mc-cap">{t('simulation.failure_rate_cap')}</label><input id="mc-cap" type="number" step="any" value={failureCap} onChange={(e) => setFailureCap(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="mc-seed">{t('simulation.seed')}</label><input id="mc-seed" type="number" value={mcSeed} onChange={(e) => setMcSeed(e.target.value)} /></div>
              <button type="button" className="btn-primary" disabled={running} onClick={submitMc}>{t('simulation.run_mc')}</button>
            </div>
          </div>
          {mcRows.length > 0 && (
            <>
              <div className="card table-scroll" role="region" aria-label={t('simulation.mc_table_caption')} tabIndex={0}>
                <table><caption className="sr-only">{t('simulation.mc_table_caption')}</caption><thead><tr><th scope="col">{t('common.time')}</th>{showMcQueueColumn && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">{t('simulation.status')}</th><th scope="col">{t('simulation.rho_mean')}</th><th scope="col">{t('simulation.rho_p95_label')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.failure_rate_ci')}</th><th scope="col">{t('simulation.precision')}</th></tr></thead>
                  <tbody>{mcRows.map((row, index) => <tr key={`${row.time}-${typeof row.queue_id === 'string' ? row.queue_id : ''}-${index}`}><th scope="row">{row.time}</th>{showMcQueueColumn && <td>{typeof row.queue_id === 'string' && row.queue_id.trim() !== '' ? row.queue_id : '—'}</td>}<td><span className={`badge ${row.status === 'PASS' ? 'badge-ok' : 'badge-bad'}`}>{row.status}</span></td><td>{fmt(row.rho_mean, 3)}</td><td>{fmt(row.rho_p95, 3)}</td><td>{fmtPct(row.failure_rate)}</td><td>{fmtFrCi(row.failure_rate_ci_lower, row.failure_rate_ci_upper)}</td><td><PrecisionBadge level={row.failure_rate_precision} /></td></tr>)}</tbody>
                </table>
              </div>
              <div className="card-grid"><div className="card"><RhoMeanP95Lines rows={mcRows} /></div><div className="card"><FailureRateBars rows={mcRows} /></div></div>
            </>
          )}
        </section>
      )}

      {!isCurrentMode && tab === 'validate' && (
        <section id="simulation-panel-validate" role="tabpanel" aria-labelledby="simulation-tab-validate" tabIndex={0}>
          <div className="card simulation-controls">
            <h3 className="section-title">{t('simulation.tabs.validate')}</h3>
            <p className="form-hint">{t('simulation.validation_saved_scenario')}</p>
            <div className="form-row">
              <div className="form-field"><label htmlFor="validation-hours">{t('simulation.validate_des_hours')}</label><input id="validation-hours" type="number" value={validationHours} onChange={(e) => setValidationHours(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="validation-trials">{t('simulation.trials')}</label><input id="validation-trials" type="number" value={validationTrials} onChange={(e) => setValidationTrials(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="validation-seed">{t('simulation.seed')}</label><input id="validation-seed" type="number" value={validationSeed} onChange={(e) => setValidationSeed(e.target.value)} /></div>
              <button type="button" className="btn-primary" disabled={running} onClick={submitValidation}>{t('simulation.validate_run')}</button>
            </div>
          </div>
          {validationRows.length > 0 && (
            <>
              {validationSettingsChanged && (
                <div role="status" className="alert alert-warn">{t('simulation.validation_settings_changed')}</div>
              )}
              {savedFailureCap === null ? (
                <div role="status" className="alert alert-warn">{t('simulation.validation_parameters_missing')}</div>
              ) : (
                <>
                  <p className="form-hint">{t('simulation.validation_saved_cap', { cap: fmtPct(savedFailureCap) })}</p>
                  <div role="status" className={`alert ${validationPassed ? 'alert-ok' : 'alert-warn'}`}>
                    {validationPassed ? t('simulation.passed') : t('simulation.failed')}
                  </div>
                </>
              )}
              <div className="card table-scroll" role="region" aria-label={t('simulation.validation_table_caption')} tabIndex={0}>
                <table><caption className="sr-only">{t('simulation.validation_table_caption')}</caption><thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('simulation.status')}</th><th scope="col">{t('simulation.sim_wq')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.precision')}</th></tr></thead>
                  <tbody>{validationRows.map((row) => <tr key={row.time}><th scope="row">{row.time}</th><td><span className={`badge ${savedFailureCap === null ? 'badge-neutral' : validationPasses(row, savedFailureCap) ? 'badge-ok' : 'badge-bad'}`}>{row.sim_status}</span></td><td>{fmt(row.sim_Wq == null ? null : row.sim_Wq * 60, 2)}</td><td>{fmtPct(row.mc_failure_rate)}</td><td><PrecisionBadge level={row.mc_failure_rate_precision} /></td></tr>)}</tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
      {isCurrentMode && (
        <>
          <div className="card simulation-controls">
            <h3 className="section-title">{t('simulation.tabs.validate')}</h3>
            {validationCurrentRows.length > 0 ? (
              <>
                {validationCurrentVerdict?.status === 'pass' && (
                  <div role="status" className="alert alert-ok">{t('simulation.passed')}</div>
                )}
                {validationCurrentVerdict?.status === 'fail' && (
                  <div role="status" className="alert alert-warn">{t('simulation.failed')}</div>
                )}
                {validationCurrentVerdict?.status === 'insufficient' && (
                  <div role="status" className="alert alert-warn">{t('decision.status.insufficient_evidence')}</div>
                )}
                <div className="card table-scroll" role="region" aria-label={t('simulation.validation_table_caption')} tabIndex={0}>
                  <table>
                    <caption className="sr-only">{t('simulation.validation_table_caption')}</caption>
                    <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('analyses.service_line')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.status')}</th></tr></thead>
                    <tbody>{validationCurrentRows.map((row, index) => (
                      <tr key={`${row.time}-${row.queue_id}-${index}`}>
                        <th scope="row">{row.time}</th>
                        <td>{row.queue_id}</td>
                        <td>{fmtPct(row.mc_failure_rate)}</td>
                        <td><span className={`badge ${row.validation_verdict === 'pass' ? 'badge-ok' : row.validation_verdict === 'fail' ? 'badge-bad' : 'badge-neutral'}`}>{row.validation_verdict}</span></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </>
            ) : hasMcCurrent ? (
              <button type="button" className="btn-primary" disabled={running} onClick={() => validationCurrentRun.mutate()}>{t('simulation.validate_run')}</button>
            ) : (
              <p className="form-hint">{t('simulation.validation_requires_mc')}</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
