import { useId, useRef, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
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
import { SeparateScheduleCard } from './SeparateScheduleCard'

type Checked = {
  result: SupervisorPreview; request: SupervisorRequest; signature: string
  setup: string; rowCount: number; applied: boolean
}
export function SupervisorSchedule({ analysis }: { analysis: AnalysisProjectOut }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const files = useQuery({ queryKey: ['datasets', analysis.id], queryFn: () => listDatasets(analysis.id) })
  const [picked, setPicked] = useState<string | null>(null)
  const datasetId = picked ?? String(currentDatasetId(files.data?.datasets) ?? '')
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
  const canApply = !!result?.can_apply && !stale && !checked?.applied && !busy
  const paired = breaks?.des.comparison.paired_wait_change
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
      setName(prev => prev || t('supervisor.default_name', { percent: numericPercent }))
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
    if (!checked || !saveEligible || busy || !name.trim()) return
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
          void qc.invalidateQueries({ queryKey: ['separate-comparison', analysis.id] })
        } catch (err) { setSelectionError(messageOf(err, t('errors.server'))) }
      }
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
          <div className="title-row"><h1 className="page-title">{t('supervisor.title')}</h1><HelpLink topic="plans" /></div>
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
        <h2>{t('supervisor.settings')}</h2>
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
        <h2>{t('supervisor.review')}</h2>
        {!result ? <>
          <p>{t('supervisor.check_first')}</p>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </> : <>
        <p role="status">{t(result.schedule.overall !== 'COMPLETE' || (breaks && !result.can_apply && !checked?.applied && result.blockers.some(b => b !== 'no_moves'))
          ? 'supervisor.needs_changes' : 'supervisor.checked')}</p>
        {result.blockers.filter(b => b !== 'break_changes_off' && !(b === 'no_moves' && checked?.applied)).length > 0 && !checked?.applied &&
          <ul className="supervisor-reasons">{result.blockers.filter(b => b !== 'break_changes_off').map(b => <li key={b}>{t('supervisor.blockers.' + b)}</li>)}</ul>}
        {result.schedule.reason && <p>{result.schedule.reason}</p>}
        {breaks && <>
          <dl className="supervisor-metrics">
            <div><dt>{t('supervisor.peak_slot')}</dt><dd>{fmtPctDecimal(breaks.peak_rho.before)} → {fmtPctDecimal(breaks.peak_rho.after)}</dd></div>
            <div><dt>{t('supervisor.wait')}</dt><dd>{fmt(breaks.des.current.summary.mean_wait_minutes)} → {fmt(breaks.des.proposed.summary.mean_wait_minutes)}</dd></div>
            <div><dt>{t('supervisor.changed_breaks')}</dt><dd>{breaks.moves.length}</dd></div>
          </dl>
          <p>{t('supervisor.wait_verdict.' + (paired?.verdict ?? 'unavailable'))}</p>
          {paired?.ci_lower != null && paired.ci_upper != null &&
            <p className="form-hint">{t('supervisor.wait_interval', { lower: fmt(paired.ci_lower), upper: fmt(paired.ci_upper), count: paired.n })}</p>}
          {breaks.moves.length > 0 && <div className="table-scroll supervisor-break-table" role="region" tabIndex={0} aria-label={t('supervisor.break_changes')}>
            <table><caption>{t('supervisor.break_changes')}</caption><thead><tr>
              <th scope="col">{t('supervisor.cashier')}</th><th scope="col">{t('supervisor.break')}</th>
              <th scope="col">{t('supervisor.current_time')}</th><th scope="col">{t('supervisor.proposed_time')}</th>
              <th scope="col">{t('supervisor.length')}</th>
            </tr></thead><tbody>{breaks.moves.map((m, i) => <tr key={i}>
              <th scope="row">{m.queue_id}</th><td>{m.label.replace(/^Break (\d+)$/, (_, n) => t('optimize.breaks_label', { number: n }))}</td>
              <td>{m.from.slice(0, 5)}</td><td>{m.to.slice(0, 5)}</td><td>{m.duration_minutes}</td>
            </tr>)}</tbody></table>
          </div>}
          {breaks.moves.length > 0 && <div className="supervisor-break-cards" aria-label={t('supervisor.break_changes')}>
            {breaks.moves.map((m, i) => <div className="supervisor-break-card" key={i}>
              <strong>{m.queue_id} · {m.label.replace(/^Break (\d+)$/, (_, n) => t('optimize.breaks_label', { number: n }))}</strong>
              <dl><div><dt>{t('supervisor.current_time')}</dt><dd>{m.from.slice(0, 5)}</dd></div>
                <div><dt>{t('supervisor.proposed_time')}</dt><dd>{m.to.slice(0, 5)}</dd></div>
                <div><dt>{t('supervisor.length')}</dt><dd>{m.duration_minutes}</dd></div></dl>
            </div>)}
          </div>}
          <details className="supervisor-advanced"><summary>{t('supervisor.break_details')}</summary>
            <p>{t('supervisor.avg_longest_line')}: {fmt(breaks.des.current.summary.max_queue)} → {fmt(breaks.des.proposed.summary.max_queue)}</p>
            <p>{t('supervisor.slot_basis')}</p>
            <div className="table-scroll" role="region" tabIndex={0} aria-label={t('supervisor.slot_details')}>
              <table><caption>{t('supervisor.slot_details')}</caption><thead><tr>
                <th scope="col">{t('optimize.sep_col_time')}</th><th scope="col">{t('supervisor.current_load')}</th><th scope="col">{t('supervisor.proposed_load')}</th>
              </tr></thead><tbody>{breaks.slots.map(s => <tr key={s.start}><th scope="row">{s.start}–{s.end}</th>
                <td>{fmtPctDecimal(s.rho_before)}</td><td>{fmtPctDecimal(s.rho_after)}</td></tr>)}</tbody></table>
            </div>
          </details>
        </>}
        <p className="form-hint">{t('supervisor.staffing_basis', { target: fmtPctDecimal(result.schedule.target_utilization), count: result.schedule.des.replications, seed: result.schedule.des.base_seed })}</p>
        <details className="supervisor-evidence"><summary>{t('supervisor.schedule_details')}</summary>
          <SeparateScheduleCard schedule={result.schedule} />
        </details>
        <p className="form-hint">{t('supervisor.claim_limit')}</p>
        <div className="supervisor-actions">
          <button ref={reviewContinueRef} type="button" onClick={() => goStep(2)}>{t('supervisor.continue_confirm')}</button>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </div>
        </>}
      </section>
      <section className="card supervisor-panel supervisor-confirm" role="tabpanel" tabIndex={0}
        id={`${panelId}-panel-2`} aria-labelledby={`${panelId}-tab-2`} hidden={step !== 2}>
        <h2>{t('supervisor.confirm')}</h2>
        {!result ? <>
          <p>{t('supervisor.check_first')}</p>
          <button type="button" className="btn-ghost" onClick={() => goStep(0)}>{t('supervisor.back_settings')}</button>
        </> : <>
        {checked?.applied ? <p role="status" className="alert alert-success">{t('supervisor.applied')}</p> :
          breaks && breaks.moves.length > 0 ? <>
            <h3>{t('supervisor.confirm_title')}</h3>
            <p>{t('supervisor.confirm_message')}</p>
            <div className="supervisor-actions">
              <button type="button" disabled={!canApply} aria-busy={busy === 'apply'} onClick={() => void apply()}>
                {t(busy === 'apply' ? 'supervisor.applying' : 'supervisor.apply')}
              </button>
              <span className="form-hint">{t('supervisor.apply_hint')}</span>
            </div>
          </> : <p>{t('supervisor.no_break_changes')}</p>}
        <div className="supervisor-save">
          <h3>{t('page2.save_scenario')}</h3>
          <label htmlFor="sup-name">{t('optimize.scenario_name')}</label>
          <input id="sup-name" value={name} onChange={e => setName(e.target.value)} disabled={!!busy} />
          {pendingMoves && <p className="form-hint">{t('supervisor.save_after_apply')}</p>}
          <div className="supervisor-actions">
            <button type="button" disabled={!saveEligible || !!busy || !name.trim()} onClick={() => void save(true)}>{t('plans.use_this_plan')}</button>
            <button type="button" className="btn-ghost" disabled={!saveEligible || !!busy || !name.trim()} onClick={() => void save(false)}>{t('plans.save_without_using')}</button>
          </div>
          {saved && !used && !stale && !selectionError && <p role="status">{t('optimize.saved')}</p>}
          {used && !stale && <p role="status">{t('plans.used')}</p>}
          {selectionError && <p role="alert">{t('plans.saved_not_used', { reason: selectionError })}</p>}
        </div>
        <div className="supervisor-actions">
          <button type="button" className="btn-ghost" disabled={!!busy} onClick={backToReview}>{t('supervisor.back_review')}</button>
        </div>
        </>}
      </section>
    </div>
  )
}
