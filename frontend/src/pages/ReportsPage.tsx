import { headingText } from '../lib/headingText'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getAnalysis, listAnalyses, listAnalysisDatasets } from '../api/analyses'
import {
  downloadReport,
  fetchReport,
  fetchReportFile,
  fetchReportPreview,
  type ReportLevel,
  type ReportPreview,
} from '../api/reports'
import { ApiState } from '../components/ui/ApiState'
import { HelpLink } from '../components/ui/HelpLink'
import { rememberLastAnalysis } from '../lib/lastAnalysis'
import { AnalysisEntry } from '../components/analysis/AnalysisEntry'
import { plainDecision } from '../lib/decisionPlain'
import { isProcessed } from '../lib/results'
import { AnalysisSelector } from '../components/analysis/AnalysisSelector'
import { fmtDecimal } from '../lib/format'

interface PreviewWithAfter extends ReportPreview {
  after_checks: { pdf: string[]; excel: string[] }
}

type Stamp = 'no_plan' | 'out_of_date' | 'plan' | 'full'

/** The full-level stamp takes the Decision's colour, as on the Decision page: only adopt is green (U10 F9). */
const DECISION_BADGE: Record<string, string> = { adopt: 'badge-ok', conditional: 'badge-warn', revise: 'badge-bad', insufficient_evidence: 'badge-warn' }

/**
 * The Decision in the reader's language, from the stored Decision's own fields (as on the Checks and Decision pages);
 * the server's English headline only when no plain answer applies. Separate-lane facts count line-periods, not
 * periods, so they are not passed as a period count.
 */
function decisionAnswer(model: ReportPreview['model'], t: TFunction): string {
  const decision = model.decision!
  const facts = decision.facts ?? {}
  const plain = plainDecision({ status: decision.status, separate: model.line_type === 'separate',
    failedPeriods: model.line_type === 'shared' ? facts.failed_periods : undefined,
    failedCount: model.line_type === 'shared' ? facts.failed_intervals : facts.failed_checks,
    totalCount: model.line_type === 'shared' ? facts.validation_intervals : facts.validation_checks,
    missing: decision.missing_evidence ?? undefined, inadequatePeriods: facts.insufficient_periods,
    todayOverloaded: facts.today_overloaded_periods })
  return plain ? t(plain.key, plain.params) : decision.headline
}

/** The reason a report request was refused, as the server wrote it. */
function refusal(error: unknown): { code: string | null; detail: string | null } {
  const data = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof data === 'string') return { code: null, detail: data }
  if (data && typeof data === 'object') {
    const value = data as { code?: unknown; detail?: unknown }
    return { code: typeof value.code === 'string' ? value.code : null, detail: typeof value.detail === 'string' ? value.detail : null }
  }
  return { code: null, detail: null }
}

/**
 * Reports (spec 2026-10-09 §7 and B8, D31-D33). The report level comes from saved results only: a plan report
 * once a current plan is selected, the full report once today's Decision gate allows it. Each card lists exactly
 * the sections and sheets of its file, as the server builds them. URL: /reports?analysis=:id
 */
export function ReportsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const id = Number(params.get('analysis'))
  const validId = Number.isInteger(id) && id > 0
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id), enabled: validId })
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id), enabled: validId })
  const plan = useQuery({
    queryKey: ['report-preview', id, 'plan'], queryFn: () => fetchReportPreview(id, 'plan') as Promise<PreviewWithAfter>,
    enabled: validId, retry: false,
  })
  const full = useQuery({
    queryKey: ['report-preview', id, 'full'], queryFn: () => fetchReportPreview(id, 'full') as Promise<PreviewWithAfter>,
    enabled: validId && plan.isSuccess, retry: false,
  })
  const [fileId, setFileId] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (analysis.data) rememberLastAnalysis(analysis.data.analysis.id)
  }, [analysis.data])

  if (!validId) {
    return <AnalysisEntry destination="reports" />
  }

  const analysisOptions = (analyses.data?.analyses ?? []).filter((item) => !item.archived_at || item.id === id)
    .map((item) => ({ id: item.id, name: item.name }))
  if (!(analyses.data?.analyses ?? []).some((item) => item.id === id)) analysisOptions.push({ id, name: analysis.data?.analysis.name ?? String(id) })
  const header = (
    <header className="page-header results-header">
      <div>
        <p className="topbar-eyebrow">{t('nav.group_insights')}</p>
        <div className="title-row"><h1 lang="en" className="page-title">{headingText(t, 'reports.title')}</h1><HelpLink topic="downloads" /></div>
      </div>
      <AnalysisSelector id="reports-analysis" label={t('results.analysis_label')} value={String(id)} options={analysisOptions} onChange={(value) => navigate(`/reports?analysis=${value}`)} />
    </header>
  )
  if (analysis.isLoading || datasets.isLoading || plan.isLoading || (plan.isSuccess && full.isLoading)) {
    return <div className="page-stack">{header}<ApiState.Loading /></div>
  }
  if (analysis.isError || datasets.isError || !analysis.data) {
    return <div className="page-stack">{header}<ApiState.ErrorState error={analysis.error ?? datasets.error} /></div>
  }

  const planRefusal = plan.isError ? refusal(plan.error) : null
  if (planRefusal && planRefusal.code !== 'no_selected_plan' && planRefusal.code !== 'plan_not_current') {
    return <div className="page-stack">{header}<ApiState.ErrorState error={plan.error} /></div>
  }
  const stamp: Stamp = planRefusal?.code === 'no_selected_plan' ? 'no_plan'
    : planRefusal ? 'out_of_date' : full.isSuccess ? 'full' : 'plan'
  const level: ReportLevel = stamp === 'full' ? 'full' : 'plan'
  const preview = stamp === 'full' ? full.data : stamp === 'plan' ? plan.data : undefined
  const fullReason = full.isError ? refusal(full.error).detail : null
  const files = (datasets.data?.datasets ?? []).filter(isProcessed)
  const chosenFile = files.find((file) => String(file.id) === fileId) ?? files[0]

  async function download(key: string, work: () => Promise<Blob>, filename: string) {
    setBusy(key)
    setMessage(null)
    try {
      downloadReport(await work(), filename)
      setMessage({ ok: true, text: t('reports.download') })
    } catch (error) {
      setMessage({ ok: false, text: refusal(error).detail ?? t('errors.server') })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="page-stack reports-page">
      {header}
      <section className="card" aria-label={t('reports.page.level')} data-testid="report-stamp">
        {stamp === 'no_plan' && (
          <>
            <h2 lang="en" className="card-title">{headingText(t, 'reports.page.no_plan_title')}</h2>
            <p>{t('reports.page.no_plan_body')}</p>
            <Link className="button-link" to={`/analyses/${id}/plans`}>{t('reports.page.go_to_plans')}</Link>
          </>
        )}
        {stamp === 'out_of_date' && (
          <div className="alert alert-warn" role="status">
            <strong>{t('reports.page.out_of_date_title')}</strong> {t('reports.page.out_of_date_body')}
            {planRefusal?.detail && <p className="form-hint">{planRefusal.detail}</p>}
            <Link to={`/analyses/${id}/plans`}>{t('reports.page.go_to_plans')}</Link>
          </div>
        )}
        {stamp === 'plan' && (
          <>
            <span className="badge badge-neutral">{t('reports.page.stamp_plan')}</span>
            <p>{t('reports.page.plan_body')}</p>
            {fullReason && <p className="form-hint" data-testid="full-reason">{fullReason}</p>}
            <Link to={`/simulation/checks?analysis=${id}&plan=suggested`}>{t('reports.page.go_to_checks')}</Link>
          </>
        )}
        {stamp === 'full' && full.data?.model.decision && (
          <>
            <span className={`badge ${DECISION_BADGE[full.data.model.decision.status] ?? 'badge-neutral'}`} data-testid="full-stamp">{t('reports.page.stamp_full', { decision: t(`decision.status.${full.data.model.decision.status}`) })}</span>
            <p data-testid="report-decision-plain">{decisionAnswer(full.data.model, t)}</p>
            {full.data.model.line_type === 'separate' && <p className="alert alert-warn" data-testid="selected-decision-scope">
              <strong>{t('decision.plain.selected_scope_label')}</strong>{' '}{t('decision.plain.selected_scope_body')}
            </p>}
          </>
        )}
        {preview && <dl className="report-context" data-testid="report-context">
          <div><dt>{t('results.plan_label')}</dt><dd>{preview.model.cover.plan_name ?? t('results.unavailable')}</dd></div>
          <div><dt>{t('reports.context.dataset')}</dt><dd>{preview.model.data?.dataset_name ?? t('results.unavailable')}
            {preview.model.data?.dataset_id != null && ` · ${t('reports.context.dataset_id', { id: preview.model.data.dataset_id })}`}</dd></div>
          {preview.model.line_type === 'shared' && typeof preview.model.assumptions?.what_if_multiplier === 'number' && Number.isFinite(preview.model.assumptions.what_if_multiplier) &&
            <div><dt>{t('reports.context.demand')}</dt><dd>{t('reports.context.multiplier', { value: fmtDecimal(preview.model.assumptions.what_if_multiplier) })}</dd></div>}
        </dl>}
      </section>

      {message && <div role={message.ok ? 'status' : 'alert'} className={`alert ${message.ok ? 'alert-ok' : 'alert-error'}`}>{message.text}</div>}

      {preview && (
        <div className="card-grid">
          {(['pdf', 'excel'] as const).map((kind) => (
            <section key={kind} className="card" aria-label={t(`reports.page.${kind}_title`)} data-testid={`report-card-${kind}`}>
              <h2 lang="en" className="card-title">{headingText(t, `reports.page.${kind}_title`)}</h2>
              <p className="form-hint">{t(`reports.page.${kind}_for`)}</p>
              <ul className="report-contents">
                {preview.contents[kind].map((item) => <li key={item}>{item}</li>)}
                {preview.after_checks[kind].map((item) => (
                  <li key={item} className="form-hint">{t('reports.page.after_checks', { item })}</li>
                ))}
              </ul>
              <button type="button" className="btn-primary" disabled={busy !== null}
                onClick={() => void download(kind, () => fetchReportFile(id, level, kind === 'pdf' ? 'pdf' : 'xlsx'),
                  `novaq_${level}_report_${id}.${kind === 'pdf' ? 'pdf' : 'xlsx'}`)}>
                {busy === kind ? t('common.loading') : t(`reports.page.${kind}_download`)}
              </button>
            </section>
          ))}
        </div>
      )}

      <section className="card" aria-label={t('reports.page.data_title')} data-testid="report-card-data">
        <h2 lang="en" className="card-title">{headingText(t, 'reports.page.data_title')}</h2>
        <p className="form-hint">{t('reports.page.data_body')}</p>
        {chosenFile ? (
          <>
            <div className="form-field">
              <label htmlFor="report-file">{t('reports.page.data_file')}</label>
              <select id="report-file" value={String(chosenFile.id)} onChange={(event) => setFileId(event.target.value)}>
                {files.map((file) => <option key={file.id} value={file.id}>{file.name}</option>)}
              </select>
            </div>
            <div className="run-bar-row">
              {(['excel', 'pdf'] as const).map((format) => (
                <button key={format} type="button" className="btn-secondary" disabled={busy !== null}
                  onClick={() => void download(`data-${format}`, () => fetchReport('datasets', chosenFile.id, format, id),
                    `novaq_data_${chosenFile.id}.${format === 'pdf' ? 'pdf' : 'xlsx'}`)}>
                  {busy === `data-${format}` ? t('common.loading') : t(`reports.page.data_${format}`)}
                </button>
              ))}
            </div>
          </>
        ) : <p>{t('results.no_files')}</p>}
      </section>
    </div>
  )
}
