import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
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

  if (datasets.isLoading || scenarios.isLoading) return <ApiState.Loading />
  if (datasets.isError || scenarios.isError) return <ApiState.ErrorState />

  const datasetList = datasets.data?.datasets ?? []
  const scenarioList = scenarios.data?.scenarios ?? []
  const effectiveDatasetId = datasetId || String(datasetList[0]?.id ?? '')
  const effectiveScenarioId = scenarioId || String(scenarioList[0]?.id ?? '')

  if (datasetList.length === 0 && scenarioList.length === 0) {
    return (
      <div>
        <h1 className="page-title">{t('reports.title')}</h1>
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
      <h1 className="page-title">{t('reports.title')}</h1>

      {downloaded && <div className="alert alert-ok">{t('reports.download')}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card" data-testid="report-card-datasets">
        <h2 className="card-title">{t('reports.source_dataset')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="report-dataset">{t('reports.source_dataset')}</label>
            <select
              id="report-dataset"
              aria-label={t('reports.source_dataset')}
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              {datasetList.length === 0 && <option value="">—</option>}
              {datasetList.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            disabled={fetching !== null || datasetList.length === 0}
            onClick={() => handleDownload('datasets', 'pdf')}
          >
            {t('reports.pdf')}
          </button>
          <button
            type="button"
            disabled={fetching !== null || datasetList.length === 0}
            onClick={() => handleDownload('datasets', 'excel')}
          >
            {t('reports.excel')}
          </button>
        </div>
      </div>

      <div className="card" data-testid="report-card-scenarios">
        <h2 className="card-title">{t('reports.source_scenario')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="report-scenario">{t('reports.source_scenario')}</label>
            <select
              id="report-scenario"
              aria-label={t('reports.source_scenario')}
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
            >
              {scenarioList.length === 0 && <option value="">—</option>}
              {scenarioList.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            disabled={fetching !== null || scenarioList.length === 0}
            onClick={() => handleDownload('scenarios', 'pdf')}
          >
            {t('reports.pdf')}
          </button>
          <button
            type="button"
            disabled={fetching !== null || scenarioList.length === 0}
            onClick={() => handleDownload('scenarios', 'excel')}
          >
            {t('reports.excel')}
          </button>
        </div>
      </div>
    </div>
  )
}
