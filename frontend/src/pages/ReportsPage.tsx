/**
 * ReportsPage - Shows the report preview (PDF/Excel sections) with download options.
 * Preview entries must stay exactly aligned with the backend generators.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { listDatasets } from '../api/datasets'
import { listScenarios } from '../api/scenarios'
import { getAnalysis } from '../api/analyses'
import {
  downloadReport,
  fetchReport,
  fetchSelectedPreview,
  fetchSelectedReport,
  reportFileExtension,
  type ReportFormat,
  type ReportKind,
} from '../api/reports'
import { ApiState } from '../components/ui/ApiState'
import { getWorkflow } from '../api/workflow'

interface ReportPreviewEntry {
  id: string
  labelKey: string
  noteKey?: string
}

interface ReportPreviewGroup {
  id: ReportFormat
  titleKey: string
  entries: ReportPreviewEntry[]
}

const REPORT_PREVIEW_GROUPS: ReportPreviewGroup[] = [
  {
    id: 'pdf',
    titleKey: 'reports.preview_pdf',
    entries: [
      { id: 'title', labelKey: 'reports.preview_pdf_title_page' },
      { id: 'executive', labelKey: 'reports.preview_pdf_executive' },
      { id: 'comparison', labelKey: 'reports.preview_pdf_comparison' },
      { id: 'recommendations', labelKey: 'reports.preview_recommendations' },
    ],
  },
  {
    id: 'excel',
    titleKey: 'reports.preview_excel',
    entries: [
      { id: 'summary', labelKey: 'reports.preview_excel_summary' },
      { id: 'segments', labelKey: 'reports.preview_excel_segments' },
      {
        id: 'recommendations',
        labelKey: 'reports.preview_recommendations',
        noteKey: 'reports.preview_excel_recommendations_note',
      },
    ],
  },
]
function formatMoney(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A'
  return `₱${value.toFixed(2)}`
}

function formatCount(value: unknown): string {
  if (typeof value !== 'number' || !Number.isInteger(value)) return '—'
  return String(value)
}

function SeparateReportView({ analysisId }: { analysisId: number }) {
  const { t } = useTranslation()
  const [fetching, setFetching] = useState<ReportFormat | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const preview = useQuery({
    queryKey: ['separate-report-preview', analysisId],
    queryFn: () => fetchSelectedPreview(analysisId),
  })
  if (preview.isLoading) return <ApiState.Loading />
  const blockedDetail = preview.isError
    ? (preview.error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
    : null
  const model = !preview.isError && preview.data
    ? (preview.data.model as unknown as Record<string, Record<string, unknown> | unknown[] | string | null>)
    : null
  const overview = ((model?.overview ?? {}) as Record<string, unknown>)
  const decision = ((model?.decision ?? {}) as Record<string, unknown>)
  const cost = ((model?.cost ?? {}) as Record<string, unknown>)
  const schedule = ((model?.schedule ?? {}) as Record<string, unknown>)
  const limitations = ((model?.limitations ?? []) as string[])
  const provenance = ((model?.provenance ?? {}) as Record<string, unknown>)
  const periods = ((schedule.periods ?? []) as Array<Record<string, unknown>>)

  async function handleDownload(format: ReportFormat) {
    setFetching(format)
    setError(null)
    setDownloaded(false)
    try {
      const blob = await fetchSelectedReport(analysisId, format)
      downloadReport(blob, `novaq_separate_${analysisId}.${reportFileExtension(format)}`)
      setDownloaded(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setFetching(null)
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('reports.eyebrow')}</div>
          <h1 className="page-title">{t('reports.sep_title')}</h1>
          <p className="page-caption">{t('reports.sep_preview')}</p>
        </div>
      </div>

      {downloaded && <div className="alert alert-ok" role="status" style={{ marginTop: '12px' }}>{t('reports.download')}</div>}
      {error && <div className="alert alert-error" role="alert" style={{ marginTop: '12px' }}>{error}</div>}
      {blockedDetail !== null && (
        <div className="alert alert-warn" role="alert" style={{ marginTop: '12px' }}>
          {typeof blockedDetail === 'string' ? blockedDetail : t('errors.server')}
        </div>
      )}

      {model !== null && (
      <>
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.sep_context')}</h3>
        <p>{t('reports.source_scenario')}: <span>{String(overview.scenario_name ?? '—')}</span></p>
        <p><span>{t('simulation.sep_decision_title')}: {String(decision.status ?? '—').toUpperCase()}</span></p>
        <p>{t('reports.source_dataset')}: <span>{String(overview.dataset_name ?? '—')}</span></p>
      </div>

      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.preview_title')}</h3>
        <div className="table-scroll" role="region" aria-label={t('reports.preview_title')} tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t('common.time')}</th>
                <th scope="col">{t('optimize.sep_col_current')}</th>
                <th scope="col">{t('optimize.sep_col_optimal')}</th>
                <th scope="col">{t('optimize.sep_col_adjustment')}</th>
                <th scope="col">{t('optimize.sep_col_peak')}</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => {
                const optimum = (period.optimum ?? {}) as Record<string, unknown>
                const activeIds = (optimum.active_queue_ids ?? []) as string[]
                return (
                  <tr key={String(period.time)}>
                    <th scope="row">{String(period.time ?? '—')}</th>
                    <td>{formatCount(period.current_count)}</td>
                    <td>
                      {formatCount(period.optimal_active_lanes)}
                      {activeIds.length > 0 && (
                        <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                          {activeIds.join(', ')}
                        </small>
                      )}
                    </td>
                    <td>{period.adjustment === null || period.adjustment === undefined ? '—' : String(period.adjustment)}</td>
                    <td>{typeof period.peak_utilization === 'number' ? `${Math.round((period.peak_utilization as number) * 100)}%` : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.sep_cost_title')}</h3>
        <p>{t('reports.sep_row_waiting')}: <span>{formatMoney(cost.current_waiting)}</span></p>
        <p>{t('reports.sep_row_selected_total')}: <span>{formatMoney(cost.selected_total)}</span></p>
        <p>{t('reports.sep_row_current_total')}: <span>N/A</span></p>
        <p>{t('reports.sep_row_savings')}: <span>N/A</span></p>
        <p>{t('reports.sep_row_roi')}: <span>N/A</span></p>
        {typeof cost.roi_unavailable_reason === 'string' && cost.roi_unavailable_reason && (
          <p className="form-hint" data-testid="separate-roi-reason">
            {t('reports.sep_row_roi_reason')}: {cost.roi_unavailable_reason}
          </p>
        )}
        {typeof cost.break_overload_note === 'string' && cost.break_overload_note && (
          <p className="form-hint" data-testid="separate-break-note">{cost.break_overload_note}</p>
        )}
      </div>

      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.sep_limitations')}</h3>
        <ul>
          {limitations.map((line, index) => (
            <li key={index} style={{ fontSize: '14px' }}>{line}</li>
          ))}
        </ul>
        <h3 className="section-title" style={{ marginTop: '12px' }}>{t('reports.sep_provenance')}</h3>
        <p className="form-hint">Scenario {String(provenance.scenario_id ?? '—')} · DES {String(provenance.des_job_id ?? '—')} · Decision {String(provenance.decision_job_id ?? '—')}</p>
      </div>
      </>
      )}

      <div className="card" data-testid="report-card-separate" style={{ marginTop: '12px', padding: '18px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            disabled={fetching !== null || model === null}
            onClick={() => handleDownload('pdf')}
            style={{ padding: '8px 16px', background: 'var(--primary)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null || model === null ? 'not-allowed' : 'pointer' }}
          >
            {fetching === 'pdf' ? '...' : t('reports.pdf')}
          </button>
          <button
            type="button"
            disabled={fetching !== null || model === null}
            onClick={() => handleDownload('excel')}
            style={{ padding: '8px 16px', background: 'var(--accent)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null || model === null ? 'not-allowed' : 'pointer' }}
          >
            {fetching === 'excel' ? '...' : t('reports.excel')}
          </button>
        </div>
      </div>
    </div>
  )
}

export function ReportsPage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
  const [datasetId, setDatasetId] = useState('')
  const [scenarioId, setScenarioId] = useState('')
  const [fetching, setFetching] = useState<ReportKind | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)

  const datasets = useQuery({ queryKey: ['datasets', analysisId], queryFn: () => listDatasets(analysisId) })
  const scenarios = useQuery({ queryKey: ['scenarios', analysisId], queryFn: () => listScenarios(analysisId) })
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => getAnalysis(analysisId!),
    enabled: Number.isInteger(analysisId),
  })
  const workflow = useQuery({
    queryKey: ['workflow', analysisId],
    queryFn: () => getWorkflow(analysisId!),
    enabled: Number.isInteger(analysisId),
  })

  if (datasets.isLoading || scenarios.isLoading || workflow.isLoading) return <ApiState.Loading />
  if (datasets.isError || scenarios.isError || workflow.isError) return <ApiState.ErrorState />

  const isSeparate = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'
  if (isSeparate && Number.isInteger(analysisId)) {
    return <SeparateReportView analysisId={analysisId as number} />
  }

  const datasetList = datasets.data?.datasets ?? []
  const scenarioList = scenarios.data?.scenarios ?? []
  const effectiveDatasetId = datasetId || String(datasetList[0]?.id ?? '')
  const effectiveScenarioId = scenarioId
    || String(workflow.data?.scenario?.id ?? scenarioList[0]?.id ?? '')
  const decision = workflow.data?.decision?.result ?? null
  const scenarioDecisionReady = Boolean(
    decision
    && decision.scenario_id === Number(effectiveScenarioId)
    && !workflow.data?.decision_stale,
  )

  if (datasetList.length === 0 && scenarioList.length === 0) {
    return (
      <div>
        {/* Topbar */}
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">{t('reports.eyebrow')}</div>
            <h1 className="page-title">{t('reports.title')}</h1>
            <p className="page-caption">{t('reports.description')}</p>
          </div>
        </div>
        <ApiState.Empty message={t('reports.empty')} />
      </div>
    )
  }

  async function handleDownload(kind: ReportKind, format: ReportFormat) {
    const id = Number(kind === 'datasets' ? effectiveDatasetId : effectiveScenarioId)
    if (!id) return
    setFetching(kind)
    setError(null)
    setDownloaded(false)
    try {
      const blob = analysisId
        ? await fetchReport(kind, id, format, analysisId)
        : await fetchReport(kind, id, format)
      downloadReport(blob, `novaq_${kind}_${id}.${reportFileExtension(format)}`)
      setDownloaded(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setFetching(null)
    }
  }

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('reports.eyebrow')}</div>
          <h1 className="page-title">{t('reports.title')}</h1>
          <p className="page-caption">{t('reports.description')}</p>
        </div>
      </div>

      {downloaded && <div className="alert alert-ok" role="status" style={{ marginTop: '12px' }}>{t('reports.download')}</div>}
      {error && <div className="alert alert-error" role="alert" style={{ marginTop: '12px' }}>{error}</div>}
      {analysisId && scenarioDecisionReady && decision && (
        <div className="card" data-testid="report-decision" style={{ marginTop: '12px' }}>
          <span className="badge badge-ok">{t('reports.decision_source')}</span>
          <h3 className="section-title">{decision.headline}</h3>
          <p>{decision.recommendation}</p>
          <p className="form-hint">{decision.provenance_warning}</p>
        </div>
      )}
      {analysisId && !scenarioDecisionReady && (
        <div className="alert alert-warn" role="status" style={{ marginTop: '12px' }}>
          {workflow.data?.decision_stale ? t('reports.decision_stale') : t('reports.decision_required')}{' '}
          <Link to={`/analyses/${analysisId}/decision`}>{t('nav.decision')}</Link>
        </div>
      )}

      {/* Report Preview */}
      <div className="card" data-testid="report-preview" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.preview_title')}</h3>
        <p className="form-hint" style={{ marginTop: '2px' }}>{t('reports.preview_hint')}</p>
        <div className="report-sections" style={{ marginTop: '12px' }}>
          {REPORT_PREVIEW_GROUPS.map((group) => (
            <section key={group.id} aria-labelledby={`report-preview-${group.id}`}>
              <h4 id={`report-preview-${group.id}`} className="report-section-title">{t(group.titleKey)}</h4>
              <ol>
                {group.entries.map((entry) => (
                  <li key={entry.id} className="report-section">
                    <strong>{t(entry.labelKey)}</strong>
                    {entry.noteKey && <span className="form-hint"> — {t(entry.noteKey)}</span>}
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </div>

      {/* Dataset Report */}
      <div className="card" data-testid="report-card-datasets" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.source_dataset')}</h3>
        <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="report-dataset" style={{ fontSize: '14px', fontWeight: 800 }}>{t('reports.source_dataset')}</label>
            <select
              id="report-dataset"
              aria-label={t('reports.source_dataset')}
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
            >
              {datasetList.length === 0 && <option value="">—</option>}
              {datasetList.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              disabled={fetching !== null || datasetList.length === 0}
              onClick={() => handleDownload('datasets', 'pdf')}
              style={{ padding: '8px 16px', background: 'var(--primary)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'datasets' ? '...' : t('reports.pdf')}
            </button>
            <button
              type="button"
              disabled={fetching !== null || datasetList.length === 0}
              onClick={() => handleDownload('datasets', 'excel')}
              style={{ padding: '8px 16px', background: 'var(--accent)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'datasets' ? '...' : t('reports.excel')}
            </button>
          </div>
        </div>
      </div>

      {/* Scenario Report */}
      <div className="card" data-testid="report-card-scenarios" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.source_scenario')}</h3>
        <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="report-scenario" style={{ fontSize: '14px', fontWeight: 800 }}>{t('reports.source_scenario')}</label>
            <select
              id="report-scenario"
              aria-label={t('reports.source_scenario')}
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
            >
              {scenarioList.length === 0 && <option value="">—</option>}
              {scenarioList.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              disabled={fetching !== null || scenarioList.length === 0 || Boolean(analysisId && !scenarioDecisionReady)}
              onClick={() => handleDownload('scenarios', 'pdf')}
              style={{ padding: '8px 16px', background: 'var(--primary)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'scenarios' ? '...' : t('reports.pdf')}
            </button>
            <button
              type="button"
              disabled={fetching !== null || scenarioList.length === 0 || Boolean(analysisId && !scenarioDecisionReady)}
              onClick={() => handleDownload('scenarios', 'excel')}
              style={{ padding: '8px 16px', background: 'var(--accent)', color: 'var(--primary-contrast)', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'scenarios' ? '...' : t('reports.excel')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
