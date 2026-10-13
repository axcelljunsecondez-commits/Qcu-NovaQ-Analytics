import simulationDefaults from '../../api/simulation-defaults.json'
import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { SimMcOut } from '../../api/types'
import {
  createWorkflowDecision,
  runSelectedDecision,
  runSelectedMc,
  runSelectedValidation,
  runWorkflowMc,
  runWorkflowMcCurrent,
  runWorkflowValidation,
  runWorkflowValidationCurrent,
} from '../../api/workflow'
import { fmt, fmtDecimal, fmtFrCi, fmtPct, fmtPctDecimal } from '../../lib/format'
import {
  MC_MAX_TRIALS,
  decisionStatusLabel,
  isSelectedDecision,
  isSelectedMcResult,
  isSelectedValidationResult,
  parseSeed,
  requestError,
  storedNumberDiffers,
  storedSeedDiffers,
  validProbability,
  validationPasses,
  validationVerdictLabel,
} from '../../lib/simulationEvidence'
import { FailureRateBars, RhoMeanP95Lines } from '../charts/Charts'
import { suggestedRun, type RunChoice, type SimulationContext } from './simulationContext'

type Status = 'done' | 'not_run' | 'pass' | 'fail' | 'insufficient'

function CheckLine({ name, required, status, children }: { name: string; required: boolean; status: Status; children?: ReactNode }) {
  const { t } = useTranslation()
  const badge = status === 'pass' || status === 'done' ? 'badge-ok' : status === 'fail' ? 'badge-bad' : status === 'insufficient' ? 'badge-warn' : 'badge-neutral'
  return (
    <details className="card check-line">
      <summary>
        <strong>{name}</strong>
        <span className="badge badge-neutral">{t(required ? 'simulation.check_required' : 'simulation.check_optional')}</span>
        <span className={`badge ${badge}`}>{t(`simulation.check_status_${status}`)}</span>
        <span className="form-hint">{t('simulation.check_details')}</span>
      </summary>
      {children}
    </details>
  )
}

function PrecisionBadge({ level }: { level: SimMcOut['failure_rate_precision'] }) {
  if (!level) return <span className="badge badge-neutral">—</span>
  const style = level === 'high' ? 'badge-ok' : level === 'moderate' ? 'badge-warn' : 'badge-bad'
  return <span className={`badge ${style}`}>{level}</span>
}

function useMcSettings(planTarget: number | null, defaultSeed: string) {
  const [trials, setTrials] = useState(String(simulationDefaults.num_trials))
  const [threshold, setThreshold] = useState(String(planTarget ?? simulationDefaults.failure_threshold))
  const [cap, setCap] = useState(String(simulationDefaults.failure_rate_cap))
  const [seed, setSeed] = useState(defaultSeed)
  return { trials, setTrials, threshold, setThreshold, cap, setCap, seed, setSeed }
}

type McSettings = ReturnType<typeof useMcSettings>

function McFields({ settings, planTarget, idPrefix }: { settings: McSettings; planTarget: number | null; idPrefix: string }) {
  const { t } = useTranslation()
  return (
    <div className="form-row">
      <div className="form-field"><label htmlFor={`${idPrefix}-trials`}>{t('simulation.trials')}</label><input id={`${idPrefix}-trials`} type="number" value={settings.trials} onChange={(e) => settings.setTrials(e.target.value)} /><span className="form-hint">{t('simulation.default_value', { value: simulationDefaults.num_trials })}</span></div>
      <div className="form-field"><label htmlFor={`${idPrefix}-threshold`}>{planTarget !== null ? t('simulation.sep_mc_threshold_plan', { target: planTarget }) : t('simulation.threshold')}</label><input id={`${idPrefix}-threshold`} type="number" step="any" value={settings.threshold} onChange={(e) => settings.setThreshold(e.target.value)} /></div>
      <div className="form-field"><label htmlFor={`${idPrefix}-cap`}>{t('simulation.failure_rate_cap')}</label><input id={`${idPrefix}-cap`} type="number" step="any" value={settings.cap} onChange={(e) => settings.setCap(e.target.value)} /><span className="form-hint">{t('simulation.default_value', { value: simulationDefaults.failure_rate_cap })}</span></div>
      <div className="form-field"><label htmlFor={`${idPrefix}-seed`}>{t('simulation.seed')}</label><input id={`${idPrefix}-seed`} type="number" step={1} value={settings.seed} onChange={(e) => settings.setSeed(e.target.value)} /></div>
    </div>
  )
}

function mcError(settings: McSettings, t: (key: string, options?: Record<string, string>) => string): string | null {
  const trials = Number(settings.trials)
  if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) return t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) })
  if (!validProbability(Number(settings.threshold))) return t('simulation.threshold_range_error')
  if (!validProbability(Number(settings.cap))) return t('simulation.cap_range_error')
  return null
}

function McTable({ rows }: { rows: SimMcOut[] }) {
  const { t } = useTranslation()
  const showLine = rows.some((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  return (
    <>
      <div className="table-scroll" role="region" aria-label={t('simulation.mc_table_caption')} tabIndex={0}>
        <table><caption className="sr-only">{t('simulation.mc_table_caption')}</caption><thead><tr><th scope="col">{t('common.time')}</th>{showLine && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">{t('simulation.status')}</th><th scope="col">{t('simulation.rho_mean')}</th><th scope="col">{t('simulation.rho_p95_label')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.failure_rate_ci')}</th><th scope="col">{t('simulation.precision')}</th></tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.time}-${typeof row.queue_id === 'string' ? row.queue_id : ''}-${index}`}><th scope="row">{row.time}</th>{showLine && <td>{typeof row.queue_id === 'string' && row.queue_id.trim() !== '' ? row.queue_id : '—'}</td>}<td><span className={`badge ${row.status === 'PASS' ? 'badge-ok' : 'badge-bad'}`}>{row.status}</span></td><td>{fmtDecimal(row.rho_mean)}</td><td>{fmtDecimal(row.rho_p95)}</td><td>{fmtPct(row.failure_rate)}</td><td>{fmtFrCi(row.failure_rate_ci_lower, row.failure_rate_ci_upper)}</td><td><PrecisionBadge level={row.failure_rate_precision} /></td></tr>)}</tbody>
        </table>
      </div>
      <div className="card-grid"><div className="card"><RhoMeanP95Lines rows={rows} /></div><div className="card"><FailureRateBars rows={rows} /></div></div>
    </>
  )
}

/** Separate-lines plan: Many variations → Results check → Decision (three existing requests). */
function SeparatePlanChecks({ context }: { context: SimulationContext }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { analysisId, planTarget, workflow } = context
  const scenario = context.scenario!
  const settings = useMcSettings(planTarget, '42')
  const [error, setError] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
  // Left at the plan target, the threshold is omitted so the backend applies (and records) the plan target.
  const thresholdIsPlanTarget = planTarget !== null && Number(settings.threshold) === planTarget
  const thresholdBelowTarget = planTarget !== null && settings.threshold.trim() !== '' && Number.isFinite(Number(settings.threshold)) && Number(settings.threshold) < planTarget
  const onError = (err: unknown) => setError(requestError(err, t('errors.server')))
  const mcRun = useMutation({
    mutationFn: () => runSelectedMc(analysisId, {
      num_trials: Number(settings.trials),
      ...(thresholdIsPlanTarget ? {} : { failure_threshold: Number(settings.threshold) }),
      failure_rate_cap: Number(settings.cap),
      seed: parseSeed(settings.seed),
    }),
    onSuccess: refresh,
    onError,
  })
  const validationRun = useMutation({ mutationFn: () => runSelectedValidation(analysisId), onSuccess: refresh, onError })
  const decisionRun = useMutation({ mutationFn: () => runSelectedDecision(analysisId), onSuccess: refresh, onError })
  const hasDes = suggestedRun(context)?.kind === 'separate'
  const mcEvidence = mcRun.data?.evidence ?? workflow.mc ?? null
  const mcResult = mcEvidence && isSelectedMcResult(mcEvidence.result) && mcEvidence.result.scenario_id === scenario.id ? mcEvidence.result : null
  const validationEvidence = validationRun.data?.evidence ?? workflow.validation ?? null
  const validationResult = validationEvidence && isSelectedValidationResult(validationEvidence.result) && validationEvidence.result.scenario_id === scenario.id ? validationEvidence.result : null
  const decisionEvidence = decisionRun.data?.evidence ?? workflow.decision ?? null
  const persisted = decisionEvidence && isSelectedDecision(decisionEvidence.result) && decisionEvidence.result.scenario_id === scenario.id ? decisionEvidence.result : null
  const fresh = decisionRun.data && isSelectedDecision(decisionRun.data.decision) && decisionRun.data.decision.scenario_id === scenario.id ? decisionRun.data.decision : null
  const decision = fresh ?? persisted
  const running = mcRun.isPending || validationRun.isPending || decisionRun.isPending

  async function checkPlan() {
    const problem = mcError(settings, t)
    if (problem) return setError(problem)
    setError(null)
    try {
      await mcRun.mutateAsync()
      await validationRun.mutateAsync()
      await decisionRun.mutateAsync()
    } catch {
      // Each step reports its own error; later steps do not run.
    }
  }

  const validationStatus: Status = validationResult ? (validationResult.verdict.status === 'pass' ? 'pass' : validationResult.verdict.status === 'fail' ? 'fail' : 'insufficient') : 'not_run'
  return (
    <div className="page-stack">
      <section className="card" aria-labelledby="decision-title">
        <h2 id="decision-title" className="section-title">{t('simulation.sep_decision_title')}</h2>
        <p className="form-hint">{t('simulation.sep_selected_plan')}: {scenario.name}</p>
        {decision ? (
          <div>
            <div role={decision.status === 'revise' || decision.status === 'insufficient_evidence' ? 'alert' : 'status'} className={`alert ${decision.status === 'revise' ? 'alert-error' : decision.status === 'conditional' || decision.status === 'adopt' ? 'alert-ok' : 'alert-warn'}`}>
              {decisionStatusLabel(decision.status, t)}
            </div>
            {decision.headline && <p className="decision-headline">{decision.headline}</p>}
            {decision.recommendation && <p>{decision.recommendation}</p>}
            <h3 className="section-title">{t('simulation.sep_decision_rationale')}</h3>
            <ul>{decision.rationale.map((line, index) => <li key={index}>{line}</li>)}</ul>
            <h3 className="section-title">{t('simulation.sep_decision_evidence')}</h3>
            <div className="table-scroll" role="region" aria-label={t('simulation.sep_decision_evidence')} tabIndex={0}>
              <table><tbody>
                <tr><th scope="row">{t('simulation.sep_lane')} Δ</th><td>{decision.facts?.lane_delta === null || decision.facts?.lane_delta === undefined ? '—' : String(decision.facts.lane_delta)}</td></tr>
                <tr><th scope="row">{t('compare.sep_row_target')}</th><td>{decision.facts?.selected_target === null || decision.facts?.selected_target === undefined ? '—' : fmtPctDecimal(decision.facts.selected_target)}</td></tr>
                <tr><th scope="row">{t('simulation.sep_col_validation')}</th><td>{decision.facts?.failed_checks ?? '—'} / {decision.facts?.validation_checks ?? '—'}</td></tr>
              </tbody></table>
            </div>
            {decision.failed_periods.length > 0 && (
              <div><h3 className="section-title">{t('simulation.sep_decision_periods')}</h3><ul>{decision.failed_periods.map((time) => <li key={time}>{time}</li>)}</ul></div>
            )}
            <div className="button-row">
              {(decision.status === 'conditional' || decision.status === 'adopt') && <Link to={`/reports?analysis=${analysisId}`}>{t('simulation.sep_decision_next_reports')}</Link>}
              {(decision.status === 'revise' || decision.status === 'insufficient_evidence') && <Link to={`/analyses/${analysisId}/plans`}>{t('simulation.sep_decision_next_compare')}</Link>}
            </div>
          </div>
        ) : <p>{t('simulation.no_decision_yet')}</p>}
        <button type="button" className="btn-primary" onClick={() => void checkPlan()} disabled={running || !hasDes}>
          {running ? t('common.loading') : t('simulation.check_the_plan')}
        </button>
        {!hasDes && <p className="form-hint">{t('simulation.sep_need_des')}</p>}
        {error && <div role="alert" className="alert alert-error">{error}</div>}
      </section>

      <CheckLine name={t('simulation.check_variations')} required status={mcResult ? 'done' : 'not_run'}>
        <p className="form-hint">{t('simulation.sep_mc_measured')} {t('simulation.variations_label')}</p>
        {thresholdBelowTarget && <div role="status" className="alert alert-warn">{t('simulation.sep_mc_threshold_below_target')}</div>}
        <McFields settings={settings} planTarget={planTarget} idPrefix="sel-mc" />
        <button type="button" className="btn-secondary" disabled={running || !hasDes} onClick={() => { const problem = mcError(settings, t); if (problem) { setError(problem); return } setError(null); mcRun.mutate() }}>{t('simulation.sep_run_mc')}</button>
        {mcResult && (
          <div className="table-scroll" role="region" aria-label={t('simulation.tabs.mc')} tabIndex={0}>
            <table>
              <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">λ</th><th scope="col">ρ</th><th scope="col">Wq (min)</th><th scope="col">{t('simulation.sep_mc_failure')}</th></tr></thead>
              <tbody>{mcResult.results.map((row, index) => (
                <tr key={`${row.time}-${row.queue_id ?? index}`}><th scope="row">{row.time}</th><td>{row.queue_id ?? '—'}</td><td>{fmt(row.lambda)}</td><td>{fmtDecimal(row.rho_mean)}</td><td>{fmt(row.Wq_mean === null ? null : row.Wq_mean * 60)}</td><td>{fmt(row.failure_rate)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </CheckLine>

      <CheckLine name={t('simulation.check_results')} required status={validationStatus}>
        <button type="button" className="btn-secondary" disabled={running || !hasDes || mcResult === null} onClick={() => { setError(null); validationRun.mutate() }}>{t('simulation.sep_run_validation')}</button>
        {(!hasDes || mcResult === null) && <p className="form-hint">{t('simulation.sep_need_validation_evidence')}</p>}
        {validationResult && (
          <>
            <div role={validationResult.verdict.status === 'pass' ? 'status' : 'alert'} className={`alert ${validationResult.verdict.status === 'pass' ? 'alert-ok' : validationResult.verdict.status === 'fail' ? 'alert-error' : 'alert-warn'}`}>
              {validationVerdictLabel(validationResult.verdict.status, t)}
            </div>
            {validationResult.verdict.status === 'insufficient' && <p className="form-hint">{t('simulation.sep_validation_missing_reason')}</p>}
            <div className="table-scroll" role="region" aria-label={t('simulation.sep_validation_title')} tabIndex={0}>
              <table>
                <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('optimize.sep_col_lanes')}</th><th scope="col">{t('simulation.sep_col_des')}</th><th scope="col">{t('simulation.sep_col_mc')}</th><th scope="col">{t('simulation.sep_col_validation')}</th></tr></thead>
                <tbody>{validationResult.periods.map((period) => (
                  <tr key={period.time}>
                    <th scope="row">{period.time}</th><td>{period.active_queue_ids.length}</td><td>{period.des_ok ? '✓' : t('simulation.sep_des_incomplete')}</td>
                    <td>{period.queues.length === 0 ? '—' : period.queues.every((q) => q.validation_verdict === 'pass') ? '✓' : period.queues.some((q) => q.validation_verdict === 'fail') ? 'FAIL' : '—'}</td>
                    <td>{period.status === 'pass' ? '✓' : period.status === 'fail' ? 'FAIL' : '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            {validationResult.periods.map((period) => (
              <details key={period.time}>
                <summary>{t('compare.sep_candidate_detail')} · {period.time}</summary>
                <div className="table-scroll" role="region" aria-label={`${t('compare.sep_candidate_detail')} · ${period.time}`} tabIndex={0}>
                  <table>
                    <thead><tr><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">ρ</th><th scope="col">Wq (min)</th><th scope="col">{t('simulation.sep_mc_failure')}</th><th scope="col">{t('simulation.sep_col_validation')}</th></tr></thead>
                    <tbody>{period.queues.map((queue) => (
                      <tr key={String(queue.queue_id)}>
                        <th scope="row">{queue.queue_id ?? '—'}</th><td>{fmtDecimal(queue.rho_sim)}</td><td>{fmt(queue.Wq_sim === null || queue.Wq_sim === undefined ? null : queue.Wq_sim * 60)}</td>
                        <td>{queue.mc_failure_rate === null || queue.mc_failure_rate === undefined ? '—' : fmt(queue.mc_failure_rate)}</td><td>{queue.validation_verdict === 'pass' ? '✓' : queue.validation_verdict === 'fail' ? 'FAIL' : '—'}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </details>
            ))}
          </>
        )}
      </CheckLine>

      <CheckLine name={t('simulation.sep_decision_title')} required status={decision ? 'done' : 'not_run'}>
        <button type="button" className="btn-secondary" disabled={running || validationResult === null} onClick={() => { setError(null); decisionRun.mutate() }}>{t('simulation.sep_run_decision')}</button>
        {validationResult === null && <p className="form-hint">{t('simulation.sep_need_validation')}</p>}
      </CheckLine>
    </div>
  )
}

/** The legacy shared path: Results check → Decision; Many variations stays optional. */
function LegacyPlanChecks({ context }: { context: SimulationContext }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { analysisId, workflow } = context
  const settings = useMcSettings(null, '')
  const [validationHours, setValidationHours] = useState('24')
  const [validationTrials, setValidationTrials] = useState('10000')
  const [validationSeed, setValidationSeed] = useState('')
  const [error, setError] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
  const onError = (err: unknown) => setError(requestError(err, t('errors.server')))
  const mcRun = useMutation({
    mutationFn: () => runWorkflowMc(analysisId, { num_trials: Number(settings.trials), failure_threshold: Number(settings.threshold), failure_rate_cap: Number(settings.cap), seed: parseSeed(settings.seed) }),
    onSuccess: refresh,
    onError,
  })
  const validationRun = useMutation({
    mutationFn: () => runWorkflowValidation(analysisId, {
      des_sim_hours: Number(validationHours), mc_trials: Number(validationTrials), mc_failure_threshold: Number(settings.threshold),
      mc_failure_rate_cap: Number(settings.cap), seed: parseSeed(validationSeed),
    }),
    onSuccess: refresh,
    onError,
  })
  const decisionRun = useMutation({ mutationFn: () => createWorkflowDecision(analysisId), onSuccess: refresh, onError })
  const mcRows = mcRun.data?.evidence.result.results ?? workflow.mc?.result.results ?? []
  const validationEvidence = validationRun.data?.evidence ?? workflow.validation
  const validationRows = validationEvidence?.result.results ?? []
  const savedCapValue = validationEvidence?.params.mc_failure_rate_cap
  const savedCap = typeof savedCapValue === 'number' && validProbability(savedCapValue) ? savedCapValue : null
  const settingsChanged = Boolean(validationEvidence) && (
    storedNumberDiffers(validationHours, validationEvidence?.params.des_sim_hours)
    || storedNumberDiffers(validationTrials, validationEvidence?.params.mc_trials)
    || storedNumberDiffers(settings.threshold, validationEvidence?.params.mc_failure_threshold)
    || storedNumberDiffers(settings.cap, validationEvidence?.params.mc_failure_rate_cap)
    || storedSeedDiffers(validationSeed, validationEvidence?.params.seed)
  )
  const passed = savedCap !== null && validationRows.length > 0 && validationRows.every((row) => validationPasses(row, savedCap))
  const decision = decisionRun.data?.decision ?? (workflow.decision_stale ? null : workflow.decision?.result ?? null)
  const running = mcRun.isPending || validationRun.isPending || decisionRun.isPending

  function validationProblem(): string | null {
    const trials = Number(validationTrials)
    const hours = Number(validationHours)
    if (!Number.isInteger(trials) || trials < 1 || trials > MC_MAX_TRIALS) return t('simulation.trials_range_error', { max: String(MC_MAX_TRIALS) })
    if (!Number.isFinite(hours) || hours <= 0 || hours > 168) return t('simulation.hours_range_error')
    if (!validProbability(Number(settings.threshold))) return t('simulation.threshold_range_error')
    if (!validProbability(Number(settings.cap))) return t('simulation.cap_range_error')
    return null
  }

  async function checkPlan() {
    const problem = validationProblem()
    if (problem) return setError(problem)
    setError(null)
    try {
      await validationRun.mutateAsync()
      await decisionRun.mutateAsync()
    } catch {
      // The failing step shows its error.
    }
  }

  return (
    <div className="page-stack">
      <section className="card" aria-labelledby="legacy-decision-title">
        <h2 id="legacy-decision-title" className="section-title">{t('simulation.sep_decision_title')}</h2>
        {decision ? (
          <div className={`alert ${decision.status === 'revise' ? 'alert-error' : decision.status === 'conditional' || decision.status === 'adopt' ? 'alert-ok' : 'alert-warn'}`} role="status">
            <strong>{t(`decision.status.${decision.status}`)}</strong> {decision.headline}
          </div>
        ) : <p>{t('simulation.no_decision_yet')}</p>}
        <Link to={`/analyses/${analysisId}/decision`}>{t('simulation.open_decision')}</Link>
        <button type="button" className="btn-primary" onClick={() => void checkPlan()} disabled={running}>{running ? t('common.loading') : t('simulation.check_the_plan')}</button>
        {error && <div role="alert" className="alert alert-error">{error}</div>}
      </section>
      <CheckLine name={t('simulation.check_results')} required status={validationRows.length === 0 ? 'not_run' : passed ? 'pass' : 'fail'}>
        <p className="form-hint">{t('simulation.validation_saved_scenario')}</p>
        <div className="form-row">
          <div className="form-field"><label htmlFor="validation-hours">{t('simulation.validate_des_hours')}</label><input id="validation-hours" type="number" value={validationHours} onChange={(e) => setValidationHours(e.target.value)} /></div>
          <div className="form-field"><label htmlFor="validation-trials">{t('simulation.trials')}</label><input id="validation-trials" type="number" value={validationTrials} onChange={(e) => setValidationTrials(e.target.value)} /></div>
          <div className="form-field"><label htmlFor="validation-seed">{t('simulation.seed')}</label><input id="validation-seed" type="number" value={validationSeed} onChange={(e) => setValidationSeed(e.target.value)} /></div>
        </div>
        <button type="button" className="btn-secondary" disabled={running} onClick={() => { const problem = validationProblem(); if (problem) { setError(problem); return } setError(null); validationRun.mutate() }}>{t('simulation.validate_run')}</button>
        {validationRows.length > 0 && (
          <>
            {settingsChanged && <div role="status" className="alert alert-warn">{t('simulation.validation_settings_changed')}</div>}
            {savedCap === null ? <div role="status" className="alert alert-warn">{t('simulation.validation_parameters_missing')}</div> : (
              <>
                <p className="form-hint">{t('simulation.validation_saved_cap', { cap: fmtPct(savedCap) })}</p>
                <div role="status" className={`alert ${passed ? 'alert-ok' : 'alert-warn'}`}>{passed ? t('simulation.passed') : t('simulation.failed')}</div>
              </>
            )}
            <div className="table-scroll" role="region" aria-label={t('simulation.validation_table_caption')} tabIndex={0}>
              <table><caption className="sr-only">{t('simulation.validation_table_caption')}</caption><thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('simulation.status')}</th><th scope="col">{t('simulation.sim_wq')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.precision')}</th></tr></thead>
                <tbody>{validationRows.map((row) => <tr key={row.time}><th scope="row">{row.time}</th><td><span className={`badge ${savedCap === null ? 'badge-neutral' : validationPasses(row, savedCap) ? 'badge-ok' : 'badge-bad'}`}>{row.sim_status}</span></td><td>{fmt(row.sim_Wq == null ? null : row.sim_Wq * 60, 2)}</td><td>{fmtPct(row.mc_failure_rate)}</td><td><PrecisionBadge level={row.mc_failure_rate_precision} /></td></tr>)}</tbody>
              </table>
            </div>
          </>
        )}
      </CheckLine>
      <CheckLine name={t('simulation.check_variations')} required={false} status={mcRows.length > 0 ? 'done' : 'not_run'}>
        <p className="form-hint">{t('simulation.variations_label')}</p>
        <McFields settings={settings} planTarget={null} idPrefix="mc" />
        <button type="button" className="btn-secondary" disabled={running} onClick={() => { const problem = mcError(settings, t); if (problem) { setError(problem); return } setError(null); mcRun.mutate() }}>{t('simulation.run_mc')}</button>
        {mcRows.length > 0 && <McTable rows={mcRows} />}
      </CheckLine>
    </div>
  )
}

/** Checks on today's staffing (no plan): Many variations, and for separate lines the Results check. */
function CurrentChecks({ context }: { context: SimulationContext }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { analysisId, workflow } = context
  const settings = useMcSettings(null, '')
  const [error, setError] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
  const onError = (err: unknown) => setError(requestError(err, t('errors.server')))
  const mcRun = useMutation({
    mutationFn: () => runWorkflowMcCurrent(analysisId, { num_trials: Number(settings.trials), failure_threshold: Number(settings.threshold), failure_rate_cap: Number(settings.cap), seed: parseSeed(settings.seed) }),
    onSuccess: refresh,
    onError,
  })
  const validationRun = useMutation({ mutationFn: () => runWorkflowValidationCurrent(analysisId), onSuccess: refresh, onError })
  const mcRows = mcRun.data?.evidence.result.results ?? workflow.mc_current?.result.results ?? []
  const validation = validationRun.data?.evidence ?? workflow.validation_current
  const validationRows = validation?.result.results ?? []
  const verdict = validation?.result.verdict ?? null
  const running = mcRun.isPending || validationRun.isPending
  const status: Status = !verdict ? 'not_run' : verdict.status === 'pass' ? 'pass' : verdict.status === 'fail' ? 'fail' : 'insufficient'
  return (
    <div className="page-stack">
      <p className="alert alert-info" role="status">{t('simulation.current_checks_note')}</p>
      {error && <div role="alert" className="alert alert-error">{error}</div>}
      <CheckLine name={t('simulation.check_variations')} required={false} status={mcRows.length > 0 ? 'done' : 'not_run'}>
        <p className="form-hint">{t('simulation.variations_label')}</p>
        <McFields settings={settings} planTarget={null} idPrefix="mc" />
        <button type="button" className="btn-secondary" disabled={running} onClick={() => { const problem = mcError(settings, t); if (problem) { setError(problem); return } setError(null); mcRun.mutate() }}>{t('simulation.run_mc')}</button>
        {mcRows.length > 0 && <McTable rows={mcRows} />}
      </CheckLine>
      <CheckLine name={t('simulation.check_results')} required={false} status={status}>
        {!context.separate ? <p className="form-hint">{t('simulation.current_validation_separate_only')}</p> : validationRows.length > 0 ? (
          <>
            {verdict?.status === 'pass' && <div role="status" className="alert alert-ok">{t('simulation.passed')}</div>}
            {verdict?.status === 'fail' && <div role="status" className="alert alert-warn">{t('simulation.failed')}</div>}
            {verdict?.status === 'insufficient' && <div role="status" className="alert alert-warn">{t('decision.status.insufficient_evidence')}</div>}
            <div className="table-scroll" role="region" aria-label={t('simulation.validation_table_caption')} tabIndex={0}>
              <table>
                <caption className="sr-only">{t('simulation.validation_table_caption')}</caption>
                <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('analyses.service_line')}</th><th scope="col">{t('simulation.failure_rate')}</th><th scope="col">{t('simulation.status')}</th></tr></thead>
                <tbody>{validationRows.map((row, index) => (
                  <tr key={`${row.time}-${row.queue_id}-${index}`}><th scope="row">{row.time}</th><td>{row.queue_id}</td><td>{fmtPct(row.mc_failure_rate)}</td>
                    <td><span className={`badge ${row.validation_verdict === 'pass' ? 'badge-ok' : row.validation_verdict === 'fail' ? 'badge-bad' : 'badge-neutral'}`}>{row.validation_verdict}</span></td></tr>
                ))}</tbody>
              </table>
            </div>
          </>
        ) : mcRows.length > 0 ? (
          <button type="button" className="btn-primary" disabled={running} onClick={() => validationRun.mutate()}>{t('simulation.validate_run')}</button>
        ) : <p className="form-hint">{t('simulation.validation_requires_mc')}</p>}
      </CheckLine>
    </div>
  )
}

/** Checks and decision (D28, D30): the Decision first, then one line per check. */
export function ChecksView({ context, run }: { context: SimulationContext; run: RunChoice }) {
  if (run === 'current') return <CurrentChecks context={context} />
  if (context.selectedSeparate) return <SeparatePlanChecks context={context} />
  return <LegacyPlanChecks context={context} />
}
