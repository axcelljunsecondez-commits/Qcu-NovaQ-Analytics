import { headingText } from '../lib/headingText'
import { useId, useRef, useState, type FormEvent } from 'react'
import { useIsMutating, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listDatasets } from '../api/datasets'
import type { AnalysisProjectOut } from '../api/types'
import { DEFAULT_OPTIONS, previewSupervisorSchedule, applySupervisorSchedule,
  type SupervisorRequest, type SupervisorPreview } from '../api/optimization'
import { createScenario } from '../api/scenarios'
import { selectWorkflowScenario } from '../api/workflow'
import { currentDatasetId, isForPlanning } from '../lib/datasets'
import { fmt, fmtPctDecimal, messageOf } from '../lib/format'
import { HelpLink } from './ui/HelpLink'
import { SavedPlanPicker } from './SavedPlanPicker'
import { Pagination } from './ui/Pagination'

type Checked = {
  result: SupervisorPreview; request: SupervisorRequest; signature: string
  setup: string; rowCount: number; applied: boolean
}

type BreakMove = NonNullable<SupervisorPreview['breaks']>['moves'][number]

function BreakMoves({ moves }: { moves: BreakMove[] }) {
  const { t } = useTranslation()
  const [pageIndex, setPageIndex] = useState(0)
  const pageSize = 4
  const pageCount = Math.ceil(moves.length / pageSize)
  const page = Math.min(pageIndex, pageCount - 1)
  const visibleMoves = moves.slice(page * pageSize, (page + 1) * pageSize)

  return (
    <>
      <div className="table-scroll supervisor-break-table" role="region" tabIndex={0} aria-label={t('supervisor.break_changes')}>
        <table>
          <caption>{t('supervisor.break_changes')}</caption>
          <thead><tr>
            <th scope="col">{t('supervisor.cashier')}</th>
            <th scope="col">{t('supervisor.current_time')}</th>
            <th scope="col">{t('supervisor.proposed_time')}</th>
            <th scope="col">{t('supervisor.length')}</th>
          </tr></thead>
          <tbody>{visibleMoves.map((move) => (
            <tr key={`${move.queue_id}-${move.from}-${move.to}`}>
              <th scope="row">{move.queue_id}<br />{move.label.replace(/^Break (\d+)$/, (_, n) => t('optimize.breaks_label', { number: n }))}</th>
              <td>{move.from.slice(0, 5)}</td>
              <td>{move.to.slice(0, 5)}</td>
              <td>{move.duration_minutes}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <Pagination page={page} pageCount={pageCount} onPageChange={setPageIndex} />
    </>
  )
}

export function SupervisorSchedule({ analysis }: { analysis: AnalysisProjectOut }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const files = useQuery({ queryKey: ['datasets', analysis.id], queryFn: () => listDatasets(analysis.id) })
  const selectingPlan = useIsMutating({ mutationKey: ['select-saved-plan', analysis.id] }) > 0
  const [picked, setPicked] = useState<string | null>(null)
  const planningId = currentDatasetId(files.data?.datasets)
  const hasPlanningFile = files.data?.datasets.some((file) => file.id === planningId && file.validation?.ok && isForPlanning(file))
  const datasetId = picked ?? String(planningId ?? '')
  const dataset = files.data?.datasets.find(d => String(d.id) === datasetId)
  const [percent, setPercent] = useState('70')
  const [allow, setAllow] = useState(false)
  const [maxMove, setMaxMove] = useState('120')
  const [serverCost, setServerCost] = useState(String(DEFAULT_OPTIONS.server_cost_per_hr))
  const [waitCost, setWaitCost] = useState(String(DEFAULT_OPTIONS.customer_waiting_cost))
  const [demand, setDemand] = useState('1')
  const [checked, setChecked] = useState<Checked | null>(null)
  const [busy, setBusy] = useState<'check' | 'apply' | 'save' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [invalid, setInvalid] = useState(false)
  const [step, setStep] = useState(0)
  const panelId = useId()
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [name, setName] = useState('')
  // A typed name is kept; otherwise the name follows the last checked busy limit.
  const [nameTyped, setNameTyped] = useState(false)
  const [saved, setSaved] = useState(false)
  const [used, setUsed] = useState(false)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const reviewContinueRef = useRef<HTMLButtonElement>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const sourceSetup = JSON.stringify(analysis.queue_setup)
  const signature = JSON.stringify({ datasetId, percent, allow, maxMove, serverCost, waitCost, demand,
    dataset })
  const stale = !!checked && (checked.signature !== signature || checked.setup !== sourceSetup)
  const result = checked?.result
  const breaks = result?.breaks
  const pendingMoves = !!breaks?.moves.length && !checked?.applied
  const breakAvailable = analysis.queue_setup.event_period_basis === 'representative_day' &&
    (analysis.queue_setup.breaks?.length ?? 0) > 0
  const saveEligible = !!result && !stale && !pendingMoves && !result.blockers.includes('not_current_data') && result.schedule.overall === 'COMPLETE' &&
    (!checked?.request.allow_break_changes || checked.applied ||
      result.blockers.every(b => b === 'no_moves'))
  const canApply = !!result?.can_apply && !stale && !checked?.applied && !busy && !selectingPlan
  const paired = breaks?.des.comparison.paired_wait_change
  const moves = breaks?.moves ?? []
  const blockers = checked?.applied ? [] : (result?.blockers ?? []).filter((blocker) => (
    blocker !== 'no_moves' && blocker !== 'break_changes_off'
  ))
  const numericPercent = percent.trim() ? Number(percent) : NaN
  const validPercent = Number.isFinite(numericPercent) && numericPercent >= 40 && numericPercent <= 90

  function goStep(next: number, focus = true) {
    setStep(next)
    if (focus) requestAnimationFrame(() => tabRefs.current[next]?.focus())
  }
  function backToReview() {
    goStep(1, false)
    requestAnimationFrame(() => (reviewContinueRef.current ?? tabRefs.current[1])?.focus())
  }

  function fieldError() {
    setInvalid(true)
    setError(t('supervisor.input_error'))
    requestAnimationFrame(() => errorRef.current?.focus())
  }
  async function check(event: FormEvent) {
    event.preventDefault()
    const cost = Number(serverCost), wait = Number(waitCost), factor = Number(demand), move = Number(maxMove)
    if (!dataset?.validation?.ok || !validPercent || !serverCost.trim() || !waitCost.trim() ||
      !demand.trim() || !Number.isFinite(cost) || cost <= 0 || !Number.isFinite(wait) || wait < 0 ||
      !Number.isFinite(factor) || factor <= 0 || (allow && (!maxMove.trim() || !Number.isInteger(move) ||
        move < 0 || move > 240 || move % 15 !== 0 || factor !== 1))) {
      fieldError(); return
    }
    const request: SupervisorRequest = {
      dataset_id: Number(datasetId), target_utilization: numericPercent / 100,
      server_cost_per_hr: cost, customer_waiting_cost: wait, lambda_multiplier: factor,
      min_active_lanes: analysis.queue_setup.queue_ids.length,
      allow_break_changes: allow, max_shift_minutes: allow ? move : 120, des: { base_seed: 42 },
    }
    setInvalid(false); setError(null); setChecked(null); setSaved(false); setUsed(false)
    setSelectionError(null); setBusy('check')
    try {
      const out = await previewSupervisorSchedule(analysis.id, request)
      setChecked({ result: out, request, signature, setup: sourceSetup,
        rowCount: dataset.row_count, applied: false })
      if (!nameTyped) setName(t('supervisor.default_name', { percent: numericPercent }))
      goStep(1)
    } catch (err) { setError(messageOf(err, t('errors.server'))) }
    finally { setBusy(null) }
  }
  async function apply() {
    if (!checked || !canApply) return
    setError(null); setBusy('apply')
    try {
      const out = await applySupervisorSchedule(analysis.id,
        { ...checked.request, preview_hash: checked.result.preview_hash })
      qc.setQueryData(['analysis', analysis.id], { analysis: out.analysis })
      setChecked({ ...checked, result: out, applied: true, setup: JSON.stringify(out.analysis.queue_setup) })
      for (const key of ['current', 'separate-comparison', 'workflow', 'scenarios']) {
        void qc.resetQueries({ queryKey: [key, analysis.id] })
      }
      void qc.invalidateQueries({ queryKey: ['analysis', analysis.id] })
    } catch (err) {
      setError(messageOf(err, t('errors.server')))
      setChecked(null)
    } finally { setBusy(null) }
  }
  async function save(use: boolean) {
    if (!checked || !saveEligible || busy || selectingPlan || !name.trim()) return
    setBusy('save'); setError(null); setSaved(false); setUsed(false); setSelectionError(null)
    const schedule = checked.result.schedule
    const options = {
      target_utilization: schedule.target_utilization,
      server_cost_per_hr: checked.request.server_cost_per_hr,
      customer_waiting_cost: checked.request.customer_waiting_cost,
      min_active_lanes: checked.request.min_active_lanes, max_active_lanes: null,
      lambda_multiplier: checked.request.lambda_multiplier, des: { ...schedule.des },
    }
    try {
      const out = await createScenario({
        name: name.trim(), analysis_id: analysis.id, dataset_id: checked.request.dataset_id,
        settings: { ...options, calculation: {
          schema_version: 2, engine_version: checked.result.engine_version,
          analysis_id: analysis.id, dataset_id: checked.request.dataset_id,
          dataset_row_count: checked.rowCount, options, calculated_at: new Date().toISOString(),
        } }, results: { schedule },
      })
      setSaved(true)
      void qc.invalidateQueries({ queryKey: ['scenarios', analysis.id] })
      if (use) {
        try {
          await selectWorkflowScenario(analysis.id, Number(out.scenario.id))
          setUsed(true)
          void qc.invalidateQueries({ queryKey: ['workflow', analysis.id] })
        } catch (err) { setSelectionError(messageOf(err, t('errors.server'))) }
      }
      void qc.invalidateQueries({ queryKey: ['separate-comparison', analysis.id] })
    } catch (err) { setError(messageOf(err, t('errors.server'))) }
    finally { setBusy(null) }
  }
  return (
    <div className="supervisor-page" onKeyDown={event => {
      if (event.key === 'Escape' && step === 2 && !busy) {
        event.preventDefault(); backToReview()
      }
    }}>
      <div className="topbar">
        <div><div className="topbar-eyebrow">{t('supervisor.eyebrow')}</div>
          <div className="title-row"><h1 lang="en" className="page-title">{headingText(t, 'supervisor.title')}</h1><HelpLink topic="plans" /></div>
          <p className="page-caption">{t('supervisor.description')}</p>
        </div>
      </div>
      <div className="supervisor-steps" role="tablist" aria-label={t('supervisor.steps')}>
        {['settings', 'review', 'confirm'].map((key, i) =>
          <button key={key} type="button" role="tab" id={`${panelId}-tab-${i}`}
            aria-controls={`${panelId}-panel-${i}`} aria-selected={step === i} tabIndex={step === i ? 0 : -1}
            ref={element => { tabRefs.current[i] = element }} onClick={() => goStep(i, false)}
            onKeyDown={event => {
              const next = event.key === 'ArrowRight' ? (i + 1) % 3 :
                event.key === 'ArrowLeft' ? (i + 2) % 3 :
                event.key === 'Home' ? 0 : event.key === 'End' ? 2 : null
              if (next !== null) { event.preventDefault(); goStep(next) }
            }}>
            <span aria-hidden="true">{i + 1}</span>{t(`supervisor.tab_${key}`)}
          </button>)}
      </div>
      {error && <div role="alert" tabIndex={-1} ref={errorRef} className="alert alert-error">{error}</div>}
      {stale && <div role="alert" className="alert alert-warn">{t('supervisor.stale')}</div>}
      <section className="card supervisor-panel supervisor-settings" role="tabpanel" tabIndex={0}
        id={`${panelId}-panel-0`} aria-labelledby={`${panelId}-tab-0`} hidden={step !== 0}>
        <h2 lang="en">{headingText(t, 'supervisor.settings')}</h2>
        <form onSubmit={check} noValidate>
        <fieldset disabled={!!busy}>
          <div className="supervisor-settings-grid">
            <div className="form-field">
              <label htmlFor="sup-file">{t('optimize.source_dataset')}</label>
              <select id="sup-file" value={datasetId} onChange={e => setPicked(e.target.value)}>
                <option value="">—</option>
                {files.data?.datasets.filter(isForPlanning).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              {files.isPending && <p role="status">{t('common.loading')}</p>}
              {files.isError && <p role="alert">{t('errors.server')}</p>}
            </div>
            <div className="form-field">
              <label htmlFor="sup-percent">{t('supervisor.busy_limit')}</label>
              <div className="supervisor-limit">
                <input type="range" min={40} max={90} step="any" value={validPercent ? numericPercent : 70}
                  aria-label={t('supervisor.busy_slider')} aria-describedby="sup-limit-hint"
                  onChange={e => setPercent(String(Math.round(Number(e.target.value) / 5) * 5))}
                  onKeyDown={e => {
                    const increment = ['ArrowRight', 'ArrowUp'].includes(e.key) ? 5 :
                      ['ArrowLeft', 'ArrowDown'].includes(e.key) ? -5 : 0
                    if (increment || e.key === 'Home' || e.key === 'End') {
                      e.preventDefault()
                      setPercent(String(e.key === 'Home' ? 40 : e.key === 'End' ? 90 :
                        Math.min(90, Math.max(40, (validPercent ? numericPercent : 70) + increment))))
                    }
                  }} />
                <div className="supervisor-percent">
                  <input id="sup-percent" type="number" inputMode="decimal" min={40} max={90} step="any"
                    value={percent} onChange={e => setPercent(e.target.value)}
                    aria-invalid={invalid && !validPercent} aria-describedby="sup-limit-hint" />
                  <span aria-hidden="true">%</span>
                </div>
              </div>
              <p className="form-hint" id="sup-limit-hint">{t('supervisor.limit_hint')}</p>
            </div>
          </div>
          <label className="supervisor-break-toggle">
            <input type="checkbox" checked={allow} disabled={!breakAvailable}
              onChange={e => setAllow(e.target.checked)} />{t('supervisor.allow_breaks')}
          </label>
          <p className="form-hint">{t(breakAvailable ? 'supervisor.break_hint' : 'supervisor.break_unavailable')}</p>
          {allow && <div className="form-field supervisor-move">
            <label htmlFor="sup-move">{t('supervisor.max_move')}</label>
            <input id="sup-move" type="number" min={0} max={240} step={15} value={maxMove}
              onChange={e => setMaxMove(e.target.value)} aria-describedby="sup-move-hint" />
            <p id="sup-move-hint" className="form-hint">{t('supervisor.move_hint')}</p>
          </div>}
          <details className="supervisor-advanced">
            <summary>{t('optimize.advanced_settings')}</summary>
            <div className="supervisor-settings-grid">
              <div className="form-field"><label htmlFor="sup-cost">{t('optimize.server_cost')}</label>
                <input id="sup-cost" type="number" step="any" min={0} value={serverCost} onChange={e => setServerCost(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="sup-wait-cost">{t('optimize.waiting_cost')}</label>
                <input id="sup-wait-cost" type="number" step="any" min={0} value={waitCost} onChange={e => setWaitCost(e.target.value)} /></div>
              <div className="form-field"><label htmlFor="sup-demand">{t('supervisor.demand')}</label>
                <input id="sup-demand" type="number" step="any" min={0} value={demand} onChange={e => setDemand(e.target.value)} aria-describedby="sup-demand-hint" />
                <p className="form-hint" id="sup-demand-hint">{t('supervisor.demand_hint')}</p></div>
            </div>
          </details>
          <div className="supervisor-actions">
            <button type="submit" aria-busy={busy === 'check'}>{t(busy === 'check' ? 'supervisor.checking' : 'supervisor.check')}</button>
            <span className="form-hint">{t('supervisor.check_hint')}</span>
          </div>
        </fieldset>
      </form>
      </section>
      <section className="card supervisor-panel supervisor-review" role="tabpanel" tabIndex={0}
        id={`${panelId}-panel-1`} aria-labelledby={`${panelId}-tab-1`} hidden={step !== 1}>
        <h2 lang="en">{headingText(t, 'supervisor.review')}</h2>
        {!result ? <>
          <p>{t('supervisor.check_first')}</p>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </> : <>
        {blockers.length > 0 && <ul className="supervisor-reasons">
          {blockers.map((blocker) => <li key={blocker}>{t('supervisor.blockers.' + blocker)}</li>)}
        </ul>}
        {result.schedule.overall !== 'COMPLETE' && result.schedule.reason && <p>{result.schedule.reason}</p>}
        {breaks && moves.length > 0 ? (
          <>
            <BreakMoves key={result.preview_hash} moves={moves} />
            <dl className="supervisor-metrics">
              <div><dt>{t('supervisor.peak_slot')}</dt><dd>{fmtPctDecimal(breaks.peak_rho.before)} → {fmtPctDecimal(breaks.peak_rho.after)}</dd></div>
              <div><dt>{t('supervisor.wait')}</dt><dd>{fmt(breaks.des.current.summary.mean_wait_minutes)} → {fmt(breaks.des.proposed.summary.mean_wait_minutes)}</dd></div>
            </dl>
            <p>{t('supervisor.wait_verdict.' + (paired?.verdict ?? 'unavailable'))}</p>
          </>
        ) : result.blockers.includes('no_moves') ? (
          <p>{t('supervisor.blockers.no_moves')}</p>
        ) : result.blockers.includes('break_changes_off') && (
          <p>{t('supervisor.blockers.break_changes_off')}</p>
        )}
        <div className="supervisor-actions">
          <button ref={reviewContinueRef} type="button" onClick={() => goStep(2)}>{t('supervisor.continue_confirm')}</button>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </div>
        </>}
      </section>
      <section className="card supervisor-panel supervisor-confirm" role="tabpanel" tabIndex={0}
        id={`${panelId}-panel-2`} aria-labelledby={`${panelId}-tab-2`} hidden={step !== 2}>
        <h2 lang="en">{headingText(t, 'supervisor.confirm')}</h2>
        {!checked ? <>
          <p>{t('supervisor.check_first')}</p>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </> : <>
        <ul>
          <li>{t('optimize.target_utilization')} · {fmtPctDecimal(checked.request.target_utilization)}</li>
          <li>{t('supervisor.allow_breaks')} · {t(checked.request.allow_break_changes ? 'guided.yes' : 'guided.no')}</li>
          {checked.request.allow_break_changes && <li>{t('supervisor.max_move')} · {checked.request.max_shift_minutes}</li>}
          {checked.request.lambda_multiplier !== 1 && <li>{t('supervisor.demand')} · {fmt(checked.request.lambda_multiplier)}</li>}
          {checked.request.server_cost_per_hr !== DEFAULT_OPTIONS.server_cost_per_hr &&
            <li>{t('optimize.server_cost')} · ₱{fmt(checked.request.server_cost_per_hr)}</li>}
          {checked.request.customer_waiting_cost !== DEFAULT_OPTIONS.customer_waiting_cost &&
            <li>{t('optimize.waiting_cost')} · ₱{fmt(checked.request.customer_waiting_cost)}</li>}
          {moves.map((move) => (
            <li key={`${move.queue_id}-${move.from}-${move.to}`}>
              {move.queue_id} · {move.from.slice(0, 5)} → {move.to.slice(0, 5)} · {t('analyses.break_minutes', { minutes: move.duration_minutes })}
            </li>
          ))}
        </ul>
        {blockers.length > 0 && <ul className="supervisor-reasons">
          {blockers.map((blocker) => <li key={blocker}>{t('supervisor.blockers.' + blocker)}</li>)}
        </ul>}
        {checked.applied ? <p role="status" className="alert alert-success">{t('supervisor.applied')}</p> :
          moves.length > 0 && <>
            <p>{t('supervisor.confirm_message')}</p>
            {step === 2 && paired?.verdict === 'no_clear_difference' && (
              <p className="form-hint">{t('supervisor.wait_verdict.no_clear_difference')}</p>
            )}
            <div className="supervisor-actions">
              <button type="button" disabled={!canApply} aria-busy={busy === 'apply'} onClick={() => void apply()}>
                {t(busy === 'apply' ? 'supervisor.applying' : 'supervisor.apply')}
              </button>
            </div>
          </>}
        <div className="supervisor-save">
          <h3 lang="en">{headingText(t, 'page2.save_scenario')}</h3>
          <label htmlFor="sup-name">{t('optimize.scenario_name')}</label>
          <input id="sup-name" value={name} onChange={e => { setName(e.target.value); setNameTyped(e.target.value !== '') }} disabled={!!busy} />
          {pendingMoves && <p className="form-hint">{t('supervisor.save_after_apply')}</p>}
          <div className="supervisor-actions">
            <button type="button" disabled={!saveEligible || !!busy || selectingPlan || !name.trim()} onClick={() => void save(true)}>{t('plans.use_this_plan')}</button>
            <button type="button" className="btn-ghost" disabled={!saveEligible || !!busy || selectingPlan || !name.trim()} onClick={() => void save(false)}>{t('plans.save_without_using')}</button>
          </div>
          {saved && !used && !stale && !selectionError && <p role="status">{t('optimize.saved')}</p>}
          {used && !stale && <p role="status">{t('plans.used')}</p>}
          {selectionError && <p role="alert">{t('plans.saved_not_used', { reason: selectionError })}</p>}
        </div>
        <div className="supervisor-actions">
          <button type="button" className="btn-ghost" disabled={!!busy} onClick={backToReview}>{t('supervisor.back_review')}</button>
        </div>
        </>}
        {step === 2 && hasPlanningFile && <SavedPlanPicker analysisId={analysis.id} separate disabled={!!busy} />}
      </section>
    </div>
  )
}
