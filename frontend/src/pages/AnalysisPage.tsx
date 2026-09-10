import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { runAnalysis, type AnalysisModel, type AnalysisRequest } from '../api/analysis'
import type { AnalysisOut } from '../api/types'
import { MetricCard } from '../components/ui/MetricCard'
import { ApiState } from '../components/ui/ApiState'
import { fmt } from '../lib/format'

const MODELS: AnalysisModel[] = ['mm1', 'mmc', 'mgc', 'mmck', 'mgck', 'erlang_a']

interface FieldDef {
  key: string
  label: string
  required: boolean
}

const FIELD_SETS: Record<AnalysisModel, FieldDef[]> = {
  mm1: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
  ],
  mmc: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
    { key: 'c', label: 'c', required: true },
  ],
  mgc: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
    { key: 'c', label: 'c', required: true },
    { key: 'variance', label: 'variance', required: true },
  ],
  mmck: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
    { key: 'c', label: 'c', required: true },
    { key: 'K', label: 'K', required: true },
  ],
  mgck: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
    { key: 'c', label: 'c', required: true },
    { key: 'variance', label: 'variance', required: true },
    { key: 'K', label: 'K', required: true },
  ],
  erlang_a: [
    { key: 'lambda', label: 'λ', required: true },
    { key: 'mu', label: 'μ', required: true },
    { key: 'c', label: 'c', required: true },
    { key: 'theta', label: 'θ', required: true },
  ],
}

function ModelExtras({ result }: { result: AnalysisOut }) {
  const extras: Array<[string, string]> = []
  if (result.blocking_probability !== undefined) {
    extras.push(['P(block)', fmt(result.blocking_probability * 100) + '%'])
  }
  if (result.effective_lambda !== undefined) {
    extras.push(['λ_eff', fmt(result.effective_lambda)])
  }
  if (result.K !== undefined) {
    extras.push(['K', String(result.K)])
  }
  if (result.rho_effective !== undefined) {
    extras.push(['ρ_eff', fmt(result.rho_effective)])
  }
  if (result.theta !== undefined) {
    extras.push(['θ', fmt(result.theta)])
  }
  if (result.lambda_eff !== undefined) {
    extras.push(['λ_eff', fmt(result.lambda_eff)])
  }
  if (result.abandonment_rate !== undefined) {
    extras.push(['abandonment', fmt(result.abandonment_rate)])
  }
  if (result.approximation) {
    extras.push(['approx', result.approximation])
  }
  if (extras.length === 0) {
    return null
  }
  return (
    <div className="card">
      <h2 className="card-title">Model metrics</h2>
      <table>
        <tbody>
          {extras.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function AnalysisPage() {
  const { t } = useTranslation()
  const [model, setModel] = useState<AnalysisModel>('mm1')
  const [values, setValues] = useState<Record<string, string>>({})
  const [result, setResult] = useState<AnalysisOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  function selectModel(next: AnalysisModel) {
    setModel(next)
    setValues({})
    setResult(null)
    setError(null)
  }

  async function handleRun() {
    setError(null)
    setRunning(true)
    const body: Record<string, number> = {}
    for (const field of FIELD_SETS[model]) {
      const raw = values[field.key]
      if (raw === undefined || raw === '') {
        if (field.required) {
          setError(`Missing parameter: ${field.label}.`)
          setRunning(false)
          return
        }
        continue
      }
      const num = Number(raw)
      if (!Number.isFinite(num)) {
        setError(`Invalid number for ${field.label}.`)
        setRunning(false)
        return
      }
      body[field.key] = num
    }
    try {
      const out = await runAnalysis(model, body as unknown as AnalysisRequest)
      setResult(out)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <h1 className="page-title">{t('analysis.title')}</h1>
      <p>{t('system.analytical_basis')}</p>
      <p className="page-caption">{t('analysis.model')}</p>

      <div className="tabs">
        {MODELS.map((m) => (
          <button
            key={m}
            type="button"
            className={`tab${model === m ? ' active' : ''}`}
            onClick={() => selectModel(m)}
          >
            {t(`analysis.tabs.${m}`)}
          </button>
        ))}
      </div>

      <div className="card">
        <h2 className="card-title">{t('analysis.params')}</h2>
        <div className="form-row">
          {FIELD_SETS[model].map((field) => (
            <div key={field.key} className="form-field">
              <label htmlFor={`analysis-${field.key}`}>{field.label}</label>
              <input
                id={`analysis-${field.key}`}
                aria-label={field.label}
                type="number"
                step="any"
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
              />
            </div>
          ))}
          <button type="button" onClick={handleRun} disabled={running}>
            {t('analysis.run')}
          </button>
        </div>
      </div>

      {running && <ApiState.Loading />}
      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <>
          <div className="card-grid">
            <MetricCard label={t('analysis.rho')} value={fmt(result.rho * 100) + '%'} />
            <MetricCard label="L" value={fmt(result.L)} />
            <MetricCard label="Lq" value={fmt(result.Lq)} />
            <MetricCard label="W (min)" value={fmt(result.W == null ? null : result.W * 60)} />
            <MetricCard label="Wq (min)" value={fmt(result.Wq == null ? null : result.Wq * 60)} />
          </div>
          <div className="card">
            <span className={`badge ${result.stable ? 'badge-ok' : 'badge-bad'}`}>
              {result.stable ? 'stable' : 'unstable'}
            </span>
          </div>
          {result.error && <div className="alert alert-error">{result.error}</div>}
          {result.metric_basis && <p className="alert alert-warn">{t('integrity.erlang_basis')}</p>}
          <ModelExtras result={result} />
        </>
      )}
    </div>
  )
}
