import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { getAnalysis, listAnalyses } from '../api/analyses'
import { getWorkflow } from '../api/workflow'
import { ApiState } from '../components/ui/ApiState'
import { NamedSharedQueueSimulation } from '../components/simulation/NamedSharedQueueSimulation'
import { SimulationModeSwitch } from '../components/simulation/SimulationModeSwitch'
import { ChecksView } from '../components/queueSimulation/ChecksView'
import { ContinuousSection } from '../components/queueSimulation/ContinuousRun'
import { KeyResultsView } from '../components/queueSimulation/KeyResultsView'
import { ReplayView } from '../components/queueSimulation/ReplayView'
import { RunBar } from '../components/queueSimulation/RunBar'
import { buildContext, defaultRun, simulationHref, type RunChoice, type SimulationPageName } from '../components/queueSimulation/simulationContext'
import { rememberLastAnalysis } from '../lib/lastAnalysis'
import { AnalysisEntry } from '../components/analysis/AnalysisEntry'
import { HelpLink } from '../components/ui/HelpLink'
import { AnalysisSelector } from '../components/analysis/AnalysisSelector'

const PAGES: Array<{ page: SimulationPageName; labelKey: string }> = [
  { page: 'results', labelKey: 'simulation.page_results' },
  { page: 'replay', labelKey: 'simulation.page_replay' },
  { page: 'checks', labelKey: 'simulation.page_checks' },
]

/**
 * Queue simulation (spec 2026-10-09 §7.8, D28): Key results, Replay and Checks and decision as
 * three pages sharing one header and run bar. URL: /simulation/<page>?analysis=&plan=&t=&mode=named
 */
export function QueueSimulationPage({ page }: { page: SimulationPageName }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const id = Number(params.get('analysis'))
  const validId = Number.isInteger(id) && id > 0
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id), enabled: validId })
  const named = analysis.data?.analysis.queue_setup.queue_structure === 'shared_queue' && params.get('mode') === 'named'
  // Named mode needs no workflow evidence: wait for the analysis to know which mode this is.
  const workflow = useQuery({ queryKey: ['workflow', id], queryFn: () => getWorkflow(id), enabled: validId && analysis.isSuccess && !named })

  useEffect(() => {
    if (analysis.data) rememberLastAnalysis(analysis.data.analysis.id)
  }, [analysis.data])

  if (!validId) {
    return <AnalysisEntry destination={`simulation/${page}`} />
  }

  const shared = analysis.data?.analysis.queue_setup.queue_structure === 'shared_queue'
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value === null) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }
  const modeSwitch = shared ? <SimulationModeSwitch mode={named ? 'named' : 'legacy'} onChange={(mode) => setParam('mode', mode === 'named' ? 'named' : null)} /> : null
  const analysisOptions = (analyses.data?.analyses ?? []).filter((item) => !item.archived_at || item.id === id)
    .map((item) => ({ id: item.id, name: item.name }))
  if (!(analyses.data?.analyses ?? []).some((item) => item.id === id)) analysisOptions.push({ id, name: analysis.data?.analysis.name ?? String(id) })
  const header = (
    <header className="page-header simulation-header">
      <div>
        <p className="topbar-eyebrow">{t('nav.group_simulation')}</p>
        <div className="title-row"><h1 className="page-title">{t('nav.queue_simulation')}</h1>{page === 'checks' ? <HelpLink topic="checks" /> : <HelpLink topic="simulation" section={page === 'replay' ? 'reading' : undefined} />}</div>
      </div>
      <AnalysisSelector id="simulation-analysis" label={t('results.analysis_label')} value={String(id)} options={analysisOptions}
        onChange={(value) => navigate(simulationHref(page, new URLSearchParams({ analysis: value })))} />
    </header>
  )

  if (analysis.isLoading || (!named && workflow.isLoading)) return <div className="page-stack">{header}<ApiState.Loading /></div>
  if (analysis.isError || !analysis.data) return <div className="page-stack">{header}<ApiState.ErrorState error={analysis.error} /></div>
  if (named) {
    // Named mode is unchanged (spec §7.8 engine coverage); it needs no plan or workflow evidence.
    return <div className="page-stack">{header}<NamedSharedQueueSimulation analysisId={id} modeSwitch={modeSwitch} /></div>
  }
  if (workflow.isError || !workflow.data) return <div className="page-stack">{header}<ApiState.ErrorState error={workflow.error} /></div>

  const context = buildContext(id, analysis.data.analysis, workflow.data)
  const requested = params.get('plan')
  const run: RunChoice = requested === 'current' || requested === 'suggested' ? requested : defaultRun(context)
  const runSwitch = (
    <div className="run-switch" role="group" aria-label={t('simulation.which_run')}>
      {(['current', 'suggested'] as const).map((choice) => (
        <button key={choice} type="button" aria-pressed={run === choice} onClick={() => setParam('plan', choice)}>
          {t(choice === 'current' ? 'simulation.run_current' : 'simulation.run_suggested')}
        </button>
      ))}
    </div>
  )
  const pageLinks = (
    <nav className="workspace-tabs" aria-label={t('simulation.pages_label')}>
      {PAGES.map((item) => (
        <NavLink key={item.page} to={simulationHref(item.page, params)} className={() => (item.page === page ? 'active' : undefined)} aria-current={item.page === page ? 'page' : undefined}>
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
  const top = <>{header}{modeSwitch}{runSwitch}{pageLinks}</>

  // A plan run needs a selected plan; say why there is none (4f/5e) and where to choose one.
  if (run === 'suggested' && !context.scenario) {
    const unavailable = context.selectionUnavailable
    return (
      <div className="page-stack">
        {top}
        {unavailable ? (
          <div role="status" className="alert alert-warn" data-testid="selection-unavailable">
            {t('simulation.selection_unavailable', { scenario: unavailable.scenarioId ?? '—', status: t(unavailable.statusKey) })}{' '}
            <Link to={`/analyses/${id}/plans`}>{t('nav.suggested_plans')}</Link>
            {unavailable.detail && <p className="form-hint">{unavailable.detail}</p>}
          </div>
        ) : (
          <div className="alert alert-warn" role="status">
            {t(context.separate && workflow.data.selection ? 'simulation.sep_stale_body' : 'simulation.select_scenario_first')}{' '}
            <Link to={`/analyses/${id}/plans`}>{t('nav.suggested_plans')}</Link>
          </div>
        )}
        <Link className="button-link" to={`/results?analysis=${id}`}>{t('simulation.choose_saved_plan')}</Link>
      </div>
    )
  }

  const periodRun = (
    <>
      <RunBar key={`run-${id}-${run}`} context={context} run={run} />
      {page === 'results' && <KeyResultsView context={context} run={run} />}
      {page === 'replay' && <ReplayView context={context} run={run} />}
      {page === 'checks' && <ChecksView key={`checks-${id}-${run}`} context={context} run={run} />}
    </>
  )

  return (
    <div className="page-stack">
      {top}
      {run === 'suggested' && context.scenario && (
        <p className="form-hint">{t('simulation.sep_selected_plan')}: {context.scenario.name} (id {context.scenario.id})</p>
      )}
      {context.separate ? periodRun : (
        <>
          {/* B4a: one shared line runs the whole day continuously; the older per-period run stays, labelled. */}
          <ContinuousSection key={`continuous-${id}`} analysisId={id} run={run} page={page} />
          <section className="page-stack older-run" aria-labelledby="older-run-title">
            <h2 id="older-run-title" className="section-title">{t('continuous.older_title')}</h2>
            <p className="form-hint">{t('continuous.older_hint')}</p>
            {periodRun}
          </section>
        </>
      )}
    </div>
  )
}
