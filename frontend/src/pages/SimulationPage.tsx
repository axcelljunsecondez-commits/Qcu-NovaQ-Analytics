import simulationDefaults from '../api/simulation-defaults.json'
import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { listDatasets, getDataset } from '../api/datasets'
import { simulateDes, simulateDesTrace, simulateMc, validateSimulation } from '../api/simulation'
import { optimizeBatch, DEFAULT_OPTIONS, type OptimizeOptions } from '../api/optimization'
import type {
  DatasetOut,
  SimDesOut,
  SimMcOut,
  SimValidateOut,
  SegmentRow,
  SimulationTrace,
} from '../api/types'
import { MetricCard } from '../components/ui/MetricCard'
import { ApiState } from '../components/ui/ApiState'
import {
  UtilizationHeatmap,
  RhoLqLines,
  MaxQueueBars,
  LqHistogram,
  RhoMeanP95Lines,
  FailureRateBars,
} from '../components/charts/Charts'
import { fmt, fmtPct, fmtFrCi, downloadCsv } from '../lib/format'
import { segmentsOf } from '../lib/queue'
import { LiveSimulationPlayback } from '../components/simulation/LiveSimulationPlayback'

type Tab = 'des' | 'mc' | 'validate' | 'live'

const TABS: Array<{ id: Tab; labelKey: string }> = [
  { id: 'des', labelKey: 'simulation.tabs.des' },
  { id: 'mc', labelKey: 'simulation.tabs.mc' },
  { id: 'validate', labelKey: 'simulation.tabs.validate' },
  { id: 'live', labelKey: 'simulation.tabs.live' },
]

function parseSeed(raw: string): number | null {
  if (raw.trim() === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function safeRho(value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0
  return value
}

function PrecisionBadge({ level }: { level: SimMcOut['failure_rate_precision'] }) {
  if (!level) {
    return <span className="badge badge-neutral">—</span>
  }
  const cls = level === 'high' ? 'badge-ok' : level === 'moderate' ? 'badge-warn' : 'badge-bad'
  return <span className={`badge ${cls}`}>{level}</span>
}

const MC_MAX_TRIALS = 100000
const FAILURE_RATE_DISPLAY_ALLOWANCE = 0.005

function isCriticalStatus(status: string | null | undefined): boolean {
  return status === 'Critical' || status === 'Unstable'
}

function isWithinFailureAllowance(rate: number | null | undefined, cap: number): boolean {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return false
  return rate <= cap || rate < cap + FAILURE_RATE_DISPLAY_ALLOWANCE
}

function failureRateBadgeClass(rate: number | null | undefined, cap: number, critical = false): string {
  if (critical || rate === null || rate === undefined || Number.isNaN(rate)) return 'badge-bad'
  if (rate <= cap) return 'badge-ok'
  if (rate < cap + FAILURE_RATE_DISPLAY_ALLOWANCE) return 'badge-warn'
  return 'badge-bad'
}

function QueueBars({ rows }: { rows: SimDesOut[] }) {
  return (
    <div className="card">
      {rows.map((row) => {
        const rho = safeRho(row.rho_sim)
        const width = Math.min(rho, 1) * 100
        const level = rho >= 1 ? 'bad' : rho >= 0.85 ? 'warn' : 'ok'
        const label = row.rho_sim === null || row.rho_sim === undefined ? '—' : Math.round(rho * 100) + '%'
        return (
          <div key={row.time} className="queue-bar-row">
            <span className="queue-bar-label">{row.time}</span>
            <div className="queue-bar-track">
              <div
                className={`queue-bar-fill ${level}`}
                style={{ width: `${width}%` }}
              />
            </div>
            <span className="queue-bar-value">{label}</span>
          </div>
        )
      })}
    </div>
  )
}

function SimulationPlayback({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [speed, setSpeed] = useState(500)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (isPlaying && rows.length > 0) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= rows.length - 1) {
            setIsPlaying(false)
            return prev
          }
          return prev + 1
        })
      }, speed)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [isPlaying, speed, rows.length])

  function handlePlay() {
    if (currentIndex >= rows.length - 1) {
      setCurrentIndex(0)
    }
    setIsPlaying(true)
  }

  function handlePause() {
    setIsPlaying(false)
  }

  function handleReset() {
    setIsPlaying(false)
    setCurrentIndex(0)
  }

  if (rows.length === 0) return null

  const currentRow = rows[currentIndex]
  const rho = safeRho(currentRow.rho_sim)
  const width = Math.min(rho, 1) * 100
  const level = rho >= 1 ? 'bad' : rho >= 0.85 ? 'warn' : 'ok'

  return (
    <div className="card simulation-playback">
      <h3>{t('simulation.playback_title')}</h3>
      <div className="playback-visual">
        <div className="playback-row">
          <span className="playback-time">{currentRow.time}</span>
          <div className="playback-bar-track">
            <div className={`playback-bar-fill ${level}`} style={{ width: `${width}%` }} />
          </div>
          <span className="playback-rho">{rho !== null ? `${Math.round(rho * 100)}%` : '—'}</span>
        </div>
        <div className="playback-stats">
          <span>Lq: {currentRow.Lq_sim !== null ? currentRow.Lq_sim.toFixed(1) : '—'}</span>
          <span>Served: {currentRow.served ?? '—'}</span>
          <span>Dropped: {currentRow.dropped ?? '—'}</span>
        </div>
      </div>
      <div className="playback-controls">
        <button type="button" onClick={handleReset} className="btn-ghost">
          {t('simulation.playback_reset')}
        </button>
        <button type="button" onClick={isPlaying ? handlePause : handlePlay} className="btn-primary">
          {isPlaying ? t('simulation.playback_pause') : t('simulation.playback_play')}
        </button>
        <div className="playback-progress">
          <span>{currentIndex + 1} / {rows.length}</span>
          <input
            type="range"
            min={0}
            max={rows.length - 1}
            value={currentIndex}
            onChange={(e) => {
              setIsPlaying(false)
              setCurrentIndex(Number(e.target.value))
            }}
          />
        </div>
        <div className="playback-speed">
          <label>{t('simulation.playback_speed')}</label>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            <option value={1000}>0.5x</option>
            <option value={500}>1x</option>
            <option value={250}>2x</option>
            <option value={100}>5x</option>
          </select>
        </div>
      </div>
    </div>
  )
}

export function SimulationPage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
  const [tab, setTab] = useState<Tab>('des')
  const queryClient = useQueryClient()
  const [vOptions, setVOptions] = useState<OptimizeOptions>(DEFAULT_OPTIONS)
  const [datasetId, setDatasetId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const [desHours, setDesHours] = useState('24')
  const [desThreshold, setDesThreshold] = useState('20')
  const [desSeed, setDesSeed] = useState('')
  const [desRows, setDesRows] = useState<SimDesOut[] | null>(null)
  const [desDirty, setDesDirty] = useState(false)
  const [liveHours, setLiveHours] = useState('1')
  const [liveMaxEvents, setLiveMaxEvents] = useState('10000')
  const [liveSeed, setLiveSeed] = useState('')
  const [liveTrace, setLiveTrace] = useState<SimulationTrace | null>(null)

  const [mcTrials, setMcTrials] = useState(String(simulationDefaults.num_trials))
  const [mcThreshold, setMcThreshold] = useState(String(simulationDefaults.failure_threshold))
  const [mcSeed, setMcSeed] = useState('')
  const [failureCap, setFailureCap] = useState(String(simulationDefaults.failure_rate_cap))
  const [mcRows, setMcRows] = useState<SimMcOut[] | null>(null)
  const [mcDirty, setMcDirty] = useState(false)

  const [validateRows, setValidateRows] = useState<SimValidateOut[] | null>(null)
  const [validateDirty, setValidateDirty] = useState(false)

  const [vTrials, setVTrials] = useState('10000')
  const [vDesHours, setVDesHours] = useState('24')
  const [vThreshold, setVThreshold] = useState(String(simulationDefaults.failure_threshold))
  const [vSeed, setVSeed] = useState('')
  const [vServerCost, setVServerCost] = useState(String(DEFAULT_OPTIONS.server_cost_per_hr))
  const [vWaitCost, setVWaitCost] = useState(String(DEFAULT_OPTIONS.customer_waiting_cost))
  const [vAbandonCost, setVAbandonCost] = useState(String(DEFAULT_OPTIONS.cost_per_abandonment))
  const [vAbandonRate, setVAbandonRate] = useState(String(DEFAULT_OPTIONS.abandonment_rate))

  const datasets = useQuery({
    queryKey: ['datasets', analysisId],
    queryFn: () => listDatasets(analysisId),
  })

  async function loadSegments(): Promise<SegmentRow[] | null> {
    const dataset = datasets.data?.datasets.find((d: DatasetOut) => String(d.id) === datasetId)
    if (!dataset) {
      setError(t('simulation.select_dataset_first'))
      return null
    }
    const loaded = await getDataset(dataset.id)
    return segmentsOf(loaded.dataset)
  }

  async function runDes() {
    const hours = Number(desHours)
    if (!Number.isFinite(hours) || hours <= 0) {
      setError(t('simulation.hours_range_error'))
      return
    }
    const threshold = Number(desThreshold)
    if (!Number.isInteger(threshold) || threshold < 1) {
      setError(t('simulation.overload_range_error'))
      return
    }
    const segments = await loadSegments()
    if (!segments) return
    setError(null)
    setRunning(true)
    try {
      const out = await simulateDes(segments, {
        sim_hours: hours,
        queue_overload_threshold: threshold,
        seed: parseSeed(desSeed),
        carryover: true,
      })
      setDesRows(out.results)
      setDesDirty(false)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  async function runLive() {
    const hours = Number(liveHours)
    if (!Number.isFinite(hours) || hours <= 0 || hours > 4) {
      setError(t('simulation.live_hours_range_error'))
      return
    }
    const maxEvents = Number(liveMaxEvents)
    if (!Number.isInteger(maxEvents) || maxEvents < 1 || maxEvents > 10000) {
      setError(t('simulation.live_events_range_error'))
      return
    }
    const segments = await loadSegments()
    if (!segments) return
    setError(null)
    setRunning(true)
    try {
      const out = await simulateDesTrace(segments, {
        trace_hours: hours,
        max_events: maxEvents,
        seed: parseSeed(liveSeed),
        carryover: true,
      })
      setLiveTrace(out)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  async function runMc() {
    const segments = await loadSegments()
    if (!segments) return
    const trials = Number(mcTrials)
    if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) {
      setError(t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) }))
      return
    }
    const threshold = Number(mcThreshold)
    if (!Number.isFinite(threshold) || threshold <= 0 || threshold > 1) {
      setError(t('simulation.threshold_range_error'))
      return
    }
    const cap = Number(failureCap)
    if (!Number.isFinite(cap) || cap <= 0 || cap > 1) {
      setError(t('simulation.cap_range_error'))
      return
    }
    setError(null)
    setRunning(true)
    try {
      const out = await simulateMc(segments, {
        num_trials: trials,
        failure_threshold: threshold,
        failure_rate_cap: cap,
        seed: parseSeed(mcSeed),
      })
      setMcRows(out.results)
      setMcDirty(false)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  async function runValidate() {
    const segments = await loadSegments()
    if (!segments) return
    const trials = Number(vTrials)
    if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) {
      setError(t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) }))
      return
    }
    const desHours = Number(vDesHours)
    if (!Number.isFinite(desHours) || desHours <= 0) {
      setError(t('simulation.hours_range_error'))
      return
    }
    const threshold = Number(vThreshold)
    if (!Number.isFinite(threshold) || threshold <= 0 || threshold > 1) {
      setError(t('simulation.threshold_range_error'))
      return
    }
    const serverCost = Number(vServerCost)
    const waitCost = Number(vWaitCost)
    const abandonCost = Number(vAbandonCost)
    if (
      !Number.isFinite(serverCost) || serverCost < 0 ||
      !Number.isFinite(waitCost) || waitCost < 0 ||
      !Number.isFinite(abandonCost) || abandonCost < 0
    ) {
      setError(t('simulation.cost_range_error'))
      return
    }
    const abandonRate = Number(vAbandonRate)
    if (!Number.isFinite(abandonRate) || abandonRate < 0 || abandonRate > 1) {
      setError(t('simulation.rate_range_error'))
      return
    }
    const cap = Number(failureCap)
    if (!Number.isFinite(cap) || cap <= 0 || cap > 1) {
      setError(t('simulation.cap_range_error'))
      return
    }
    setError(null)
    setRunning(true)
    try {
      const optimized = await optimizeBatch(segments, {
        ...vOptions,
        target_utilization: vOptions.target_utilization,
        server_cost_per_hr: serverCost,
        customer_waiting_cost: waitCost,
        max_servers: vOptions.max_servers,
        cost_per_abandonment: abandonCost,
        abandonment_rate: abandonRate,
      })
      const comparisonRows = optimized.results.map((r, index) => ({ ...segments[index], ...r, lambda: r.lambda_ }))
      const out = await validateSimulation(comparisonRows as unknown as Record<string, unknown>[], {
        des_sim_hours: desHours,
        mc_trials: trials,
        mc_failure_threshold: threshold,
        mc_failure_rate_cap: cap,
        seed: parseSeed(vSeed),
      })
      setValidateRows(out.results)
      setValidateDirty(false)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  const desStable = desRows
    ? desRows.filter((r) => r.status === 'Lean' || r.status === 'Normal' || r.status === 'Peak').length
    : 0
  const desCritical = desRows ? desRows.filter((r) => r.status === 'Critical').length : 0
  const desServed = desRows ? desRows.reduce((acc, r) => acc + r.served, 0) : 0
  const desDropped = desRows ? desRows.reduce((acc, r) => acc + r.dropped, 0) : 0
  const currentFailureCap = Number(failureCap)
  const rowPasses = (r: SimValidateOut) =>
    r.simulation_supported !== false && !r.validation_reason && r.sim_status !== 'ERROR' &&
    !isCriticalStatus(r.sim_status) &&
    isWithinFailureAllowance(r.mc_failure_rate, currentFailureCap)
  const allPassed = validateRows !== null && validateRows.length > 0 && validateRows.every(rowPasses)
  const failedRows = validateRows?.filter((r) => !rowPasses(r)) ?? []

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">Simulation · Stress-Test the Plan Under Realistic Variability</div>
          <h1 className="page-title">{t('simulation.title')}</h1>
          <p className="page-caption">Stress-test the staffing plan with queueing simulation to ensure reliability.</p>
        </div>
      </div>
      <p style={{ fontSize: '11px', color: '#76889e', marginTop: '4px' }}>{t('integrity.simulation_coverage')}</p>
      {[...(desRows ?? []), ...(mcRows ?? []), ...(validateRows ?? [])].filter((r) => r.simulation_supported === false).map((r, index) =>
        <div role="alert" className="alert alert-warn" key={index}>{r.time}: {r.selected_model ?? '—'} — {t('integrity.unsupported')}</div>)}

      {/* Dataset Selector */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('page1.data_source')}</h3>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="sim-dataset" style={{ fontSize: '11px', fontWeight: 800 }}>{t('optimize.source_dataset')}</label>
            <select
              id="sim-dataset"
              aria-label={t('optimize.source_dataset')}
              value={datasetId}
              onChange={(e) => {
                setDatasetId(e.target.value)
                const prior = queryClient.getQueryData<OptimizeOptions>(['optimization-options', e.target.value]) ?? DEFAULT_OPTIONS
                setVOptions(prior)
                setVServerCost(String(prior.server_cost_per_hr))
                setVWaitCost(String(prior.customer_waiting_cost))
                setVAbandonCost(String(prior.cost_per_abandonment))
                setVAbandonRate(String(prior.abandonment_rate))
                setDesRows(null)
                setDesDirty(true)
                setLiveTrace(null)
                setMcRows(null)
                setMcDirty(true)
                setValidateRows(null)
                setValidateDirty(true)
              }}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
            >
              <option value="">—</option>
              {datasets.data?.datasets.map((d: DatasetOut) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map((tItem) => (
          <button
            key={tItem.id}
            type="button"
            role="tab"
            aria-selected={tab === tItem.id}
            className={`tab${tab === tItem.id ? ' active' : ''}`}
            onClick={() => {
              setTab(tItem.id)
              setError(null)
            }}
          >
            {t(tItem.labelKey)}
          </button>
        ))}
      </div>

      {running && <ApiState.Loading />}
      {error && <div className="alert alert-error">{error}</div>}

      {tab === 'des' && (
        <div>
          <div className="card">
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="des-hours">{t('simulation.hours')}</label>
                <input
                  id="des-hours"
                  type="number"
                  step="any"
                  value={desHours}
                  onChange={(e) => {
                    setDesHours(e.target.value)
                    setDesRows(null)
                    setDesDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="des-threshold">{t('simulation.overload')}</label>
                <input
                  id="des-threshold"
                  type="number"
                  step="any"
                  value={desThreshold}
                  onChange={(e) => {
                    setDesThreshold(e.target.value)
                    setDesRows(null)
                    setDesDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="des-seed">{t('simulation.seed')}</label>
                <input
                  id="des-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={desSeed}
                  onChange={(e) => {
                    setDesSeed(e.target.value)
                    setDesRows(null)
                    setDesDirty(true)
                  }}
                />
              </div>
              <button type="button" onClick={runDes} disabled={running}>
                {t('simulation.run_des')}
              </button>
            </div>
          </div>

          {desDirty && !desRows && (
            <p className="form-hint">{t('simulation.stale_hint')}</p>
          )}

          {desRows && (
            <>
              <div className="card-grid">
                <MetricCard label={t('simulation.stable')} value={desStable} />
                <MetricCard label={t('simulation.critical')} value={desCritical} />
                <MetricCard label={t('simulation.served')} value={desServed} />
                <MetricCard label={t('simulation.dropped')} value={desDropped} />
              </div>
              <SimulationPlayback rows={desRows} />
              <QueueBars rows={desRows} />
              <div className="card-grid">
                <div className="card">
                  <UtilizationHeatmap rows={desRows} />
                </div>
                <div className="card">
                  <RhoLqLines rows={desRows} />
                </div>
              </div>
              <div className="card-grid">
                <div className="card">
                  <MaxQueueBars rows={desRows} />
                </div>
                <div className="card">
                  <LqHistogram rows={desRows} />
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => downloadCsv('novaq_des_simulation.csv', desRows as unknown as Array<Record<string, unknown>>)}
              >
                {t('simulation.download_csv')}
              </button>
            </>
          )}
        </div>
      )}

      {tab === 'live' && (
        <div>
          <div className="card">
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="live-hours">{t('simulation.live_hours')}</label>
                <input
                  id="live-hours"
                  type="number"
                  min={0.01}
                  max={4}
                  step="any"
                  value={liveHours}
                  onChange={(event) => {
                    setLiveHours(event.target.value)
                    setLiveTrace(null)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="live-max-events">{t('simulation.live_max_events')}</label>
                <input
                  id="live-max-events"
                  type="number"
                  min={1}
                  max={10000}
                  step={1}
                  value={liveMaxEvents}
                  onChange={(event) => {
                    setLiveMaxEvents(event.target.value)
                    setLiveTrace(null)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="live-seed">{t('simulation.seed')}</label>
                <input
                  id="live-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={liveSeed}
                  onChange={(event) => {
                    setLiveSeed(event.target.value)
                    setLiveTrace(null)
                  }}
                />
              </div>
              <button type="button" onClick={runLive} disabled={running}>
                {t('simulation.live_run')}
              </button>
            </div>
            <p className="form-hint">{t('simulation.live_scope')}</p>
          </div>

          {liveTrace
            ? <LiveSimulationPlayback trace={liveTrace} />
            : <div className="card live-no-run" role="status">{t('simulation.live_run_prompt')}</div>}
        </div>
      )}

      {tab === 'mc' && (
        <div>
          <div className="card">
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="mc-trials">{t('simulation.trials')}</label>
                <input
                  id="mc-trials"
                  type="number"
                  step="any"
                  min={1}
                  max={MC_MAX_TRIALS}
                  value={mcTrials}
                  onChange={(e) => {
                    setMcTrials(e.target.value)
                    setMcRows(null)
                    setMcDirty(true)
                  }}
                />
                <p className="form-hint">{t('simulation.trials_help')}</p>
              </div>
              <div className="form-field">
                <label htmlFor="mc-threshold">{t('simulation.threshold')}</label>
                <input
                  id="mc-threshold"
                  type="number"
                  step="any"
                  value={mcThreshold}
                  onChange={(e) => {
                    setMcThreshold(e.target.value)
                    setMcRows(null)
                    setMcDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="mc-failure-cap">{t('simulation.failure_rate_cap')}</label>
                <input
                  id="mc-failure-cap"
                  aria-label={t('simulation.failure_rate_cap')}
                  type="number"
                  step="any"
                  value={failureCap}
                  onChange={(e) => {
                    setFailureCap(e.target.value)
                    setMcRows(null)
                    setMcDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="mc-seed">{t('simulation.seed')}</label>
                <input
                  id="mc-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={mcSeed}
                  onChange={(e) => {
                    setMcSeed(e.target.value)
                    setMcRows(null)
                    setMcDirty(true)
                  }}
                />
              </div>
              <button type="button" onClick={runMc} disabled={running}>
                {t('simulation.run_mc')}
              </button>
            </div>
          </div>

          {mcDirty && !mcRows && (
            <p className="form-hint">{t('simulation.stale_hint')}</p>
          )}

          {mcRows && (
            <>
              <div className="card">
                <table>
                  <thead>
                    <tr>
                      <th>{t('optimize.segment')}</th>
                      <th>{t('simulation.status')}</th>
                      <th>{t('simulation.rho_mean')}</th>
                      <th>{t('simulation.rho_p95_label')}</th>
                      <th>{t('simulation.lq_mean')}</th>
                      <th>{t('simulation.wq_mean')}</th>
                      <th>{t('simulation.failure_rate')}</th>
                      <th>{t('simulation.failure_rate_ci')}</th>
                      <th>{t('simulation.precision')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mcRows.map((row) => (
                      <tr key={row.time}>
                        <td>{row.time}</td>
                        <td>
                          <span className={`badge ${failureRateBadgeClass(row.failure_rate, currentFailureCap)}`}>
                            {row.status}
                          </span>
                        </td>
                        <td>{fmt(row.rho_mean, 3)}</td>
                        <td>{fmt(row.rho_p95, 3)}</td>
                        <td>{fmt(row.Lq_mean, 2)}</td>
                        <td>{fmt(row.Wq_mean, 2)}</td>
                        <td>{fmtPct(row.failure_rate)}</td>
                        <td>{fmtFrCi(row.failure_rate_ci_lower, row.failure_rate_ci_upper)}</td>
                        <td><PrecisionBadge level={row.failure_rate_precision} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card-grid">
                <div className="card">
                  <RhoMeanP95Lines rows={mcRows} />
                </div>
                <div className="card">
                  <FailureRateBars rows={mcRows} />
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => downloadCsv('novaq_mc_simulation.csv', mcRows as unknown as Array<Record<string, unknown>>)}
              >
                {t('simulation.download_csv')}
              </button>
            </>
          )}
        </div>
      )}

      {tab === 'validate' && (
        <div>
          <div className="card">
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="v-target">{t('system.planning_target')}</label>
                <input id="v-target" type="number" step="any" value={vOptions.target_utilization} onChange={(e) => { setVOptions((o) => ({...o, target_utilization: Number(e.target.value)})); setValidateRows(null) }} />
                <label htmlFor="v-min">{t('system.min_servers')}</label>
                <input id="v-min" type="number" min={1} value={vOptions.min_servers ?? 1} onChange={(e) => { setVOptions((o) => ({...o, min_servers: Number(e.target.value)})); setValidateRows(null) }} />
                <label htmlFor="v-max">{t('system.max_servers')}</label>
                <input id="v-max" type="number" min={1} value={vOptions.max_servers ?? 24} onChange={(e) => { setVOptions((o) => ({...o, max_servers: Number(e.target.value)})); setValidateRows(null) }} />
                <label htmlFor="v-wait">{t('system.max_wait')}</label>
                <input id="v-wait" type="number" min={0} step="any" value={vOptions.max_wait_minutes ?? ''} onChange={(e) => { setVOptions((o) => ({...o, max_wait_minutes: e.target.value === '' ? null : Number(e.target.value)})); setValidateRows(null) }} />
                <label htmlFor="v-trials">{t('simulation.trials')}</label>
                <input
                  id="v-trials"
                  aria-label={t('simulation.trials')}
                  type="number"
                  step="any"
                  min={1}
                  max={MC_MAX_TRIALS}
                  value={vTrials}
                  onChange={(e) => {
                    setVTrials(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-des-hours">{t('simulation.validate_des_hours')}</label>
                <input
                  id="v-des-hours"
                  aria-label={t('simulation.validate_des_hours')}
                  type="number"
                  step="any"
                  value={vDesHours}
                  onChange={(e) => {
                    setVDesHours(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-threshold">{t('simulation.threshold')}</label>
                <input
                  id="v-threshold"
                  aria-label={t('simulation.threshold')}
                  type="number"
                  step="any"
                  value={vThreshold}
                  onChange={(e) => {
                    setVThreshold(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-failure-cap">{t('simulation.failure_rate_cap')}</label>
                <input
                  id="v-failure-cap"
                  aria-label={t('simulation.failure_rate_cap')}
                  type="number"
                  step="any"
                  value={failureCap}
                  onChange={(e) => {
                    setFailureCap(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-seed">{t('simulation.seed')}</label>
                <input
                  id="v-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={vSeed}
                  onChange={(e) => {
                    setVSeed(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-server-cost">{t('optimize.server_cost')}</label>
                <input
                  id="v-server-cost"
                  aria-label={t('optimize.server_cost')}
                  type="number"
                  step="any"
                  value={vServerCost}
                  onChange={(e) => {
                    setVServerCost(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-wait-cost">{t('optimize.waiting_cost')}</label>
                <input
                  id="v-wait-cost"
                  aria-label={t('optimize.waiting_cost')}
                  type="number"
                  step="any"
                  value={vWaitCost}
                  onChange={(e) => {
                    setVWaitCost(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-aband-cost">{t('optimize.abandonment_cost')}</label>
                <input
                  id="v-aband-cost"
                  aria-label={t('optimize.abandonment_cost')}
                  type="number"
                  step="any"
                  value={vAbandonCost}
                  onChange={(e) => {
                    setVAbandonCost(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-aband-rate">{t('optimize.abandonment_rate')}</label>
                <input
                  id="v-aband-rate"
                  aria-label={t('optimize.abandonment_rate')}
                  type="number"
                  step="any"
                  value={vAbandonRate}
                  onChange={(e) => {
                    setVAbandonRate(e.target.value)
                    setValidateRows(null)
                    setValidateDirty(true)
                  }}
                />
              </div>
              <button type="button" onClick={runValidate} disabled={running}>
                {t('simulation.validate_run')}
              </button>
            </div>
          </div>

          {validateDirty && !validateRows && (
            <p className="form-hint">{t('simulation.stale_hint')}</p>
          )}

          {validateRows && (
            <>
              <div className={`alert ${allPassed ? 'alert-ok' : 'alert-error'}`}>
                {allPassed ? t('simulation.passed') : t('simulation.failed')}
              </div>
              <div className="card">
                <table>
                  <thead>
                    <tr>
                      <th>{t('optimize.segment')}</th>
                      <th>{t('simulation.status')}</th>
                      <th>sim_ρ</th>
                      <th>{t('system.sim_wait_minutes')}</th>
                      <th>sim max queue</th>
                      <th>{t('simulation.failure_rate')}</th>
                      <th>{t('simulation.failure_rate_ci')}</th>
                      <th>MC ρ mean</th>
                      <th>MC ρ p95</th>
                      <th>MC Wq CI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {validateRows.map((row) => (
                      <tr key={row.time}>
                        <td>{row.time}</td>
                        <td>
                          <span
                            className={`badge ${failureRateBadgeClass(
                              row.mc_failure_rate,
                              currentFailureCap,
                              isCriticalStatus(row.sim_status),
                            )}`}
                          >
                            {row.sim_status}
                          </span>
                        </td>
                        <td>{fmt(row.sim_rho, 3)}</td>
                        <td>{fmt(row.sim_Wq == null ? null : row.sim_Wq * 60, 3)}</td>
                        <td>{row.sim_max_queue}</td>
                        <td>{fmtPct(row.mc_failure_rate)}</td>
                        <td>{fmtFrCi(row.mc_failure_rate_ci_lower, row.mc_failure_rate_ci_upper)}</td>
                        <td>{fmt(row.mc_rho_mean, 3)}</td>
                        <td>{fmt(row.mc_rho_p95, 3)}</td>
                        <td>{row.mc_Wq_ci}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={`validation-verdict ${allPassed ? 'is-passed' : 'has-risk'}`}>
                {allPassed
                  ? t('simulation.verdict_passed', {
                      cap: String(Math.round(Number(failureCap) * 100)),
                    })
                  : t('simulation.verdict_residual', {
                      failed: String(failedRows.length),
                      cap: String(Math.round(Number(failureCap) * 100)),
                    })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
