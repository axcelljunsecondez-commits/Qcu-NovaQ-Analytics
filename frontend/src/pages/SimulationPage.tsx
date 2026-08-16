import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { listDatasets, getDataset } from '../api/datasets'
import { simulateDes, simulateMc, validateSimulation } from '../api/simulation'
import { optimizeBatch, DEFAULT_OPTIONS } from '../api/optimization'
import type { DatasetOut, SimDesOut, SimMcOut, SimValidateOut } from '../api/types'
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

type Tab = 'des' | 'mc' | 'validate'

interface SegmentRow {
  time: string
  lambda: number
  mu: number
  c: number
}

const TABS: Array<{ id: Tab; labelKey: string }> = [
  { id: 'des', labelKey: 'simulation.tabs.des' },
  { id: 'mc', labelKey: 'simulation.tabs.mc' },
  { id: 'validate', labelKey: 'simulation.tabs.validate' },
]

function segmentsOf(dataset: DatasetOut): SegmentRow[] {
  return (dataset.normalized ?? []).map((row) => ({
    time: String(row.time),
    lambda: Number(row.lambda),
    mu: Number(row.mu),
    c: Number(row.c),
  }))
}

function parseSeed(raw: string): number | null {
  if (raw.trim() === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function safeRho(value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0
  return value
}

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return value.toFixed(digits)
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return Math.round(value * 100) + '%'
}

function fmtFrCi(lower: number | null | undefined, upper: number | null | undefined): string {
  if (lower === null || upper === null || lower === undefined || upper === undefined || Number.isNaN(lower) || Number.isNaN(upper)) {
    return '—'
  }
  return `${Math.round(lower * 100)}%–${Math.round(upper * 100)}%`
}

function PrecisionBadge({ level }: { level: SimMcOut['failure_rate_precision'] }) {
  if (!level) {
    return <span className="badge badge-neutral">—</span>
  }
  const cls = level === 'high' ? 'badge-ok' : level === 'moderate' ? 'badge-warn' : 'badge-bad'
  return <span className={`badge ${cls}`}>{level}</span>
}

const MC_MAX_TRIALS = 100000

function downloadCsv(filename: string, rows: Array<Record<string, unknown>>) {
  if (rows.length === 0) return
  const header = Object.keys(rows[0])
  const lines = [
    header.join(','),
    ...rows.map((row) => header.map((h) => String(row[h] ?? '')).join(',')),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
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

export function SimulationPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('des')
  const [datasetId, setDatasetId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const [desHours, setDesHours] = useState('24')
  const [desThreshold, setDesThreshold] = useState('20')
  const [desSeed, setDesSeed] = useState('42')
  const [desRows, setDesRows] = useState<SimDesOut[] | null>(null)

  const [mcTrials, setMcTrials] = useState('2000')
  const [mcThreshold, setMcThreshold] = useState('0.75')
  const [mcSeed, setMcSeed] = useState('42')
  const [mcRows, setMcRows] = useState<SimMcOut[] | null>(null)

  const [validateRows, setValidateRows] = useState<SimValidateOut[] | null>(null)

  const [vTrials, setVTrials] = useState('10000')
  const [vThreshold, setVThreshold] = useState('0.75')
  const [vSeed, setVSeed] = useState('')
  const [vServerCost, setVServerCost] = useState(String(DEFAULT_OPTIONS.server_cost_per_hr))
  const [vWaitCost, setVWaitCost] = useState(String(DEFAULT_OPTIONS.customer_waiting_cost))
  const [vAbandonCost, setVAbandonCost] = useState(String(DEFAULT_OPTIONS.cost_per_abandonment))
  const [vAbandonRate, setVAbandonRate] = useState(String(DEFAULT_OPTIONS.abandonment_rate))

  const datasets = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets(),
  })

  async function loadSegments(): Promise<SegmentRow[] | null> {
    const dataset = datasets.data?.datasets.find((d: DatasetOut) => String(d.id) === datasetId)
    if (!dataset) {
      setError('Select a dataset first.')
      return null
    }
    const loaded = await getDataset(dataset.id)
    return segmentsOf(loaded.dataset)
  }

  async function runDes() {
    const segments = await loadSegments()
    if (!segments) return
    setError(null)
    setRunning(true)
    try {
      const out = await simulateDes(segments, {
        sim_hours: Number(desHours),
        queue_overload_threshold: Number(desThreshold),
        seed: parseSeed(desSeed),
        carryover: true,
      })
      setDesRows(out.results)
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
    setError(null)
    setRunning(true)
    try {
      const out = await simulateMc(segments, {
        num_trials: trials,
        failure_threshold: Number(mcThreshold),
        seed: parseSeed(mcSeed),
      })
      setMcRows(out.results)
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
    setError(null)
    setRunning(true)
    try {
      const optimized = await optimizeBatch(segments, {
        target_utilization: DEFAULT_OPTIONS.target_utilization,
        server_cost_per_hr: Number(vServerCost),
        customer_waiting_cost: Number(vWaitCost),
        max_servers: DEFAULT_OPTIONS.max_servers,
        cost_per_abandonment: Number(vAbandonCost),
        abandonment_rate: Number(vAbandonRate),
      })
      const comparisonRows = optimized.results.map((r) => ({ ...r, lambda: r.lambda_ }))
      const out = await validateSimulation(comparisonRows as unknown as Record<string, unknown>[], {
        mc_trials: trials,
        mc_failure_threshold: Number(vThreshold),
        seed: parseSeed(vSeed),
      })
      setValidateRows(out.results)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  const desStable = desRows ? desRows.filter((r) => r.status !== 'Critical').length : 0
  const desCritical = desRows ? desRows.filter((r) => r.status === 'Critical').length : 0
  const desServed = desRows ? desRows.reduce((acc, r) => acc + r.served, 0) : 0
  const desDropped = desRows ? desRows.reduce((acc, r) => acc + r.dropped, 0) : 0
  const allAdequate = validateRows !== null && validateRows.every((r) => r.mc_adequate)

  return (
    <div>
      <h1 className="page-title">{t('simulation.title')}</h1>
      <p className="page-caption">{t('page3.caption')}</p>

      <div className="card">
        <h2 className="card-title">{t('page1.data_source')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="sim-dataset">{t('optimize.source_dataset')}</label>
            <select
              id="sim-dataset"
              aria-label={t('optimize.source_dataset')}
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
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
            onClick={() => setTab(tItem.id)}
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
                  onChange={(e) => setDesHours(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="des-threshold">{t('simulation.overload')}</label>
                <input
                  id="des-threshold"
                  type="number"
                  step="any"
                  value={desThreshold}
                  onChange={(e) => setDesThreshold(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="des-seed">{t('simulation.seed')}</label>
                <input
                  id="des-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={desSeed}
                  onChange={(e) => setDesSeed(e.target.value)}
                />
              </div>
              <button type="button" onClick={runDes} disabled={running}>
                {t('simulation.run_des')}
              </button>
            </div>
          </div>

          {desRows && (
            <>
              <div className="card-grid">
                <MetricCard label={t('simulation.stable')} value={desStable} />
                <MetricCard label={t('simulation.critical')} value={desCritical} />
                <MetricCard label={t('simulation.served')} value={desServed} />
                <MetricCard label={t('simulation.dropped')} value={desDropped} />
              </div>
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
                  onChange={(e) => setMcTrials(e.target.value)}
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
                  onChange={(e) => setMcThreshold(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="mc-seed">{t('simulation.seed')}</label>
                <input
                  id="mc-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={mcSeed}
                  onChange={(e) => setMcSeed(e.target.value)}
                />
              </div>
              <button type="button" onClick={runMc} disabled={running}>
                {t('simulation.run_mc')}
              </button>
            </div>
          </div>

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
                          <span className={`badge ${row.status === 'FAIL' ? 'badge-bad' : 'badge-ok'}`}>
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
                <label htmlFor="v-trials">{t('simulation.trials')}</label>
                <input
                  id="v-trials"
                  aria-label={t('simulation.trials')}
                  type="number"
                  step="any"
                  min={1}
                  max={MC_MAX_TRIALS}
                  value={vTrials}
                  onChange={(e) => setVTrials(e.target.value)}
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
                  onChange={(e) => setVThreshold(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="v-seed">{t('simulation.seed')}</label>
                <input
                  id="v-seed"
                  aria-label={t('simulation.seed')}
                  type="text"
                  value={vSeed}
                  onChange={(e) => setVSeed(e.target.value)}
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
                  onChange={(e) => setVServerCost(e.target.value)}
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
                  onChange={(e) => setVWaitCost(e.target.value)}
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
                  onChange={(e) => setVAbandonCost(e.target.value)}
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
                  onChange={(e) => setVAbandonRate(e.target.value)}
                />
              </div>
              <button type="button" onClick={runValidate} disabled={running}>
                {t('simulation.validate_run')}
              </button>
            </div>
          </div>

          {validateRows && (
            <>
              <div className={`alert ${allAdequate ? 'alert-ok' : 'alert-error'}`}>
                {allAdequate ? t('simulation.passed') : t('simulation.failed')}
              </div>
              <div className="card">
                <table>
                  <thead>
                    <tr>
                      <th>{t('optimize.segment')}</th>
                      <th>{t('simulation.status')}</th>
                      <th>sim_ρ</th>
                      <th>sim_Wq</th>
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
                          <span className={`badge ${row.mc_adequate ? 'badge-ok' : 'badge-bad'}`}>
                            {row.sim_status}
                          </span>
                        </td>
                        <td>{fmt(row.sim_rho, 3)}</td>
                        <td>{fmt(row.sim_Wq, 3)}</td>
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
            </>
          )}
        </div>
      )}
    </div>
  )
}
