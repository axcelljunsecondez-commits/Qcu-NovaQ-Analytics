import { useEffect, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { getAnalysis, getAnalysisCurrent, listAnalyses, listAnalysisDatasets } from '../api/analyses'
import { getObservedWait } from '../api/workflow'
import { ApiState } from '../components/ui/ApiState'
import { BusyStrip } from '../components/results/BusyStrip'
import { FileSelector } from '../components/results/FileSelector'
import { KeyResults } from '../components/results/KeyResults'
import { PlanChanges } from '../components/results/PlanChanges'
import { ArrivalsChart, WaitByPeriodChart, WorkloadChart } from '../components/results/ResultsCharts'
import { ResultsDetails } from '../components/results/ResultsDetails'
import { useSelectedPlan } from '../components/results/useSelectedPlan'
import { currentDatasetId } from '../lib/datasets'
import { rememberLastAnalysis, resolveLastAnalysis, storedLastAnalysis, subscribeLastAnalysis } from '../lib/lastAnalysis'
import { ALL } from '../lib/periodFilter'
import { hasCustomerRecords, isProcessed, lineOf } from '../lib/results'
import { HelpLink } from '../components/ui/HelpLink'

/**
 * Analysis results (spec 2026-10-09 §7.7, D14–D21, D31): the results of any successfully
 * processed file, read-only, plus "What the plan changes" for the planning file.
 * URL: /results?analysis=:id&file=:datasetId&period=&line=
 */
export function ResultsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const id = Number(params.get('analysis'))
  const validId = Number.isInteger(id) && id > 0
  const stored = useSyncExternalStore(subscribeLastAnalysis, storedLastAnalysis, () => null)
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id), enabled: validId })
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id), enabled: validId })

  const files = (datasets.data?.datasets ?? []).filter(isProcessed)
  const planningId = currentDatasetId(datasets.data?.datasets)
  const requested = Number(params.get('file'))
  const selected = files.find((file) => file.id === requested) ?? files.find((file) => file.id === planningId) ?? files[0]
  const isPlanningFile = selected !== undefined && selected.id === planningId
  const fileId = selected?.id

  // The planning file is read the usual way (same request and cache entry as Data and setup);
  // any other file is read by its id (B3) and never touches plans, selection or simulation.
  const current = useQuery({
    queryKey: ['current', id, fileId],
    queryFn: () => getAnalysisCurrent(id, isPlanningFile ? undefined : fileId),
    enabled: fileId !== undefined,
    retry: false,
  })
  const records = hasCustomerRecords(selected)
  const observed = useQuery({
    queryKey: ['observed-wait', id, fileId],
    queryFn: () => getObservedWait(id, isPlanningFile ? undefined : fileId),
    enabled: fileId !== undefined && records,
    retry: false,
  })
  const separate = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'
  const plan = useSelectedPlan(id, separate, isPlanningFile && analysis.isSuccess)

  useEffect(() => {
    if (analysis.data) rememberLastAnalysis(analysis.data.analysis.id)
  }, [analysis.data])

  if (!validId) {
    if (analyses.isLoading) return <ApiState.Loading />
    const last = resolveLastAnalysis(analyses.data?.analyses, stored)
    return <Navigate to={last ? `/results?analysis=${last}` : '/analyses'} replace />
  }

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === ALL) next.delete(key)
      else next.set(key, value)
    }
    setParams(next, { replace: true })
  }
  const period = params.get('period') ?? ALL
  const line = params.get('line') ?? ALL

  const header = (
    <header className="page-header results-header">
      <div>
        <p className="topbar-eyebrow">{t('nav.group_insights')}</p>
        <div className="title-row"><h1 className="page-title">{t('nav.analysis_results')}</h1><HelpLink topic="results" /></div>
      </div>
      <div className="form-field">
        <label htmlFor="results-analysis">{t('results.analysis_label')}</label>
        <select id="results-analysis" value={String(id)} onChange={(event) => navigate(`/results?analysis=${event.target.value}`)}>
          {(analyses.data?.analyses ?? []).filter((item) => !item.archived_at || item.id === id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          {!(analyses.data?.analyses ?? []).some((item) => item.id === id) && <option value={id}>{analysis.data?.analysis.name ?? id}</option>}
        </select>
      </div>
    </header>
  )

  if (analysis.isLoading || datasets.isLoading) return <div className="page-stack">{header}<ApiState.Loading /></div>
  if (analysis.isError || datasets.isError || !analysis.data) return <div className="page-stack">{header}<ApiState.ErrorState error={analysis.error ?? datasets.error} /></div>
  if (!selected) {
    return (
      <div className="page-stack">
        {header}
        <ApiState.Empty message={t('results.no_files')} />
        <Link className="button-link" to={`/analyses/${id}/data`}>{t('nav.data_setup')}</Link>
      </div>
    )
  }

  const rows = current.data?.rows ?? []
  const separateRows = rows.some((row) => lineOf(row) !== null)
  const planTarget = isPlanningFile && (plan.kind === 'shared' || plan.kind === 'separate') ? plan.target : null

  return (
    <div className="page-stack">
      {header}
      <FileSelector files={files} selected={selected} onSelect={(fileValue) => update({ file: fileValue === planningId ? null : String(fileValue), period: null, line: null })} />

      {!isPlanningFile && (
        <div className="alert alert-info" role="status" data-testid="results-review-banner">
          <strong>{t('results.reviewing_banner')}</strong>
          <p>{t('results.recalculated_note')}</p>
          {planningId === null && <p>{t('results.no_planning_file')}</p>}
        </div>
      )}

      {current.isLoading ? <ApiState.Loading /> : current.isError || !current.data ? (
        <ApiState.ErrorState error={current.error} />
      ) : current.data.dataset.id !== selected.id ? <ApiState.Loading /> : (
        <>
          <section aria-labelledby="key-results-title">
            <h2 id="key-results-title" className="section-title">{t('results.key_results')}</h2>
            <KeyResults
              rows={rows}
              kpis={current.data.kpis}
              separate={separateRows}
              recorded={{ hasRecords: records, loading: observed.isLoading, dayWaitHours: observed.data?.available ? observed.data.day_observed_wait : null }}
              busiest={current.data.busiest_period}
            />
          </section>
          <BusyStrip rows={rows} planTarget={planTarget} period={period === ALL ? null : period} onPeriod={(time) => update({ period: time })} />
          <div className="grid g2">
            <ArrivalsChart periods={current.data.arrivals_by_period} />
            <WorkloadChart rows={rows} separate={separateRows} />
          </div>
          {records && observed.data?.available && observed.data.dataset_id === selected.id && <WaitByPeriodChart periods={observed.data.periods} />}
          {isPlanningFile && <PlanChanges analysisId={id} plan={plan} />}
          <ResultsDetails
            rows={rows}
            explanations={current.data.explanations}
            selectedModel={current.data.selected_model}
            period={period}
            line={line}
            onPeriod={(value) => update({ period: value })}
            onLine={(value) => update({ line: value })}
          />
        </>
      )}
    </div>
  )
}
