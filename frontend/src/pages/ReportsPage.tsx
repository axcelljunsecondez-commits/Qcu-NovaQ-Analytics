/**
 * ReportsPage - Shows report preview with 10 sections and download options.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { listDatasets } from '../api/datasets'
import { listScenarios } from '../api/scenarios'
import {
  downloadReport,
  fetchReport,
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
  const workflow = useQuery({
    queryKey: ['workflow', analysisId],
    queryFn: () => getWorkflow(analysisId!),
    enabled: Number.isInteger(analysisId),
  })

  if (datasets.isLoading || scenarios.isLoading || workflow.isLoading) return <ApiState.Loading />
  if (datasets.isError || scenarios.isError || workflow.isError) return <ApiState.ErrorState />

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
