import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  createContinuousRun,
  getClosingPolicy,
  getContinuousCompatibility,
  getContinuousPlayback,
  getContinuousRun,
  listContinuousRuns,
  putClosingPolicy,
  type ClosingPolicy,
  type ContinuousCompatibility,
  type ContinuousPlan,
  type ContinuousPlayback,
  type ContinuousReason,
  type ContinuousRunOut,
} from '../../api/continuous'
import { fmtDecimal } from '../../lib/format'
import { clockAt, clockOfMinutes, hoursAt, latestRunIds, rangeText, stateAt, waitingSteps } from '../../lib/continuous'
import { requestError } from '../../lib/simulationEvidence'
import type { SimulationPageName } from './simulationContext'

const SPEEDS = [0.25, 0.5, 1, 2, 5, 10]
const SECONDS_AT_1X = 60 // replay speed semantics unchanged (D29 base rate still open): 1× plays the day in 60 s

function useContinuous(analysisId: number) {
  const closing = useQuery({ queryKey: ['closing-policy', analysisId], queryFn: () => getClosingPolicy(analysisId) })
  const compatibility = useQuery({ queryKey: ['continuous-compat', analysisId], queryFn: () => getContinuousCompatibility(analysisId) })
  const runs = useQuery({ queryKey: ['continuous-runs', analysisId], queryFn: () => listContinuousRuns(analysisId) })
  const latest = latestRunIds(runs.data?.runs ?? [])
  const current = useQuery({
    queryKey: ['continuous-run', analysisId, latest.current], queryFn: () => getContinuousRun(analysisId, latest.current as number),
    enabled: latest.current !== undefined,
  })
  const suggested = useQuery({
    queryKey: ['continuous-run', analysisId, latest.suggested], queryFn: () => getContinuousRun(analysisId, latest.suggested as number),
    enabled: latest.suggested !== undefined,
  })
  return { closing, compatibility, runs, current: current.data ?? null, suggested: suggested.data ?? null }
}

function ReasonList({ reasons }: { reasons: ContinuousReason[] }) {
  const { t } = useTranslation()
  return (
    <ul className="reason-list">
      {reasons.map((reason) => (
        <li key={reason.code}>
          {t(`continuous.reason.${reason.code}`, { defaultValue: reason.code })}
          {reason.problems && <ul>{reason.problems.map((problem) => <li key={problem}>{problem}</li>)}</ul>}
          {reason.periods && <span> {reason.periods.join(', ')}</span>}
          {reason.detail && <span className="form-hint"> {reason.detail}</span>}
        </li>
      ))}
    </ul>
  )
}

function ClosingRule({ analysisId, rule }: { analysisId: number; rule: ClosingPolicy | null }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(rule === null)
  const [choice, setChoice] = useState<ClosingPolicy | null>(rule)
  const save = useMutation({
    mutationFn: (value: ClosingPolicy) => putClosingPolicy(analysisId, value),
    onSuccess: () => {
      setEditing(false)
      void queryClient.invalidateQueries({ queryKey: ['closing-policy', analysisId] })
      void queryClient.invalidateQueries({ queryKey: ['continuous-compat', analysisId] })
    },
  })
  if (!editing && rule !== null) {
    return (
      <span data-testid="closing-rule">
        <strong>{t('continuous.closing_title')}:</strong> {t(`continuous.closing_${rule}`)}{' '}
        <button type="button" className="btn-ghost btn-inline" onClick={() => { setChoice(rule); setEditing(true) }}>{t('continuous.change')}</button>
      </span>
    )
  }
  return (
    <fieldset className="closing-choice" data-testid="closing-choice">
      <legend>{rule === null ? t('continuous.closing_none') : t('continuous.closing_title')}</legend>
      {(['DRAIN', 'HARD_CUTOFF'] as const).map((value) => (
        <label key={value} className="radio-row">
          <input type="radio" name={`closing-${analysisId}`} value={value} checked={choice === value} onChange={() => setChoice(value)} />
          {t(`continuous.closing_${value}`)}
        </label>
      ))}
      <p className="form-hint">{t('continuous.rule_future_only')}</p>
      <div className="button-row">
        <button type="button" className="btn-secondary" disabled={choice === null || save.isPending} onClick={() => choice && save.mutate(choice)}>{t('continuous.save_rule')}</button>
        {rule !== null && <button type="button" className="btn-ghost" onClick={() => setEditing(false)}>{t('continuous.cancel')}</button>}
      </div>
      {save.isError && <div role="alert" className="alert alert-error">{requestError(save.error, t('errors.server'))}</div>}
    </fieldset>
  )
}

function staleNotes(run: ContinuousRunOut, t: (key: string) => string): string[] {
  const notes: string[] = []
  if (!run.setup_matches_current) notes.push(t('continuous.stale_setup'))
  if (!run.dataset_is_current) notes.push(t('continuous.stale_data'))
  if (run.plan_is_selected === false) notes.push(t('continuous.stale_plan'))
  return notes
}

/** The run bar for the full-day run: hours, closing rule, status, Run full operation, Advanced (D24, D30). */
function ContinuousRunBar({ analysisId, plan, compatibility, rule, stored }: {
  analysisId: number
  plan: ContinuousPlan
  compatibility: ContinuousCompatibility
  rule: ClosingPolicy | null
  stored: ContinuousRunOut | null
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const view = compatibility.plans[plan]
  const [repeats, setRepeats] = useState(String(compatibility.default_replications))
  const [seed, setSeed] = useState(String(compatibility.default_seed))
  const [error, setError] = useState<string | null>(null)
  const run = useMutation({
    mutationFn: () => createContinuousRun(analysisId, { plan, replications: Number(repeats), seed: Number(seed) }),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['continuous-runs', analysisId] })
    },
    onError: (failure) => setError(requestError(failure, t('errors.server'))),
  })
  const max = compatibility.limits.max_replications
  const start = () => {
    const count = Number(repeats)
    if (!Number.isInteger(count) || count < 1 || count > max) return setError(t('continuous.repeats_range', { max }))
    const seedValue = Number(seed)
    if (!Number.isInteger(seedValue) || seedValue < 0) return setError(t('continuous.seed_range'))
    if (view.expected_customers_per_day !== null && view.expected_customers_per_day * count > compatibility.limits.max_expected_customers_per_run) {
      return setError(t('continuous.over_limit', { max: compatibility.limits.max_expected_customers_per_run }))
    }
    run.mutate()
  }
  const hours = view.horizon ? `${clockOfMinutes(view.horizon.start_minute)}–${clockOfMinutes(view.horizon.end_minute)}` : null
  const blocking = view.reasons.filter((reason) => reason.code !== 'no_closing_policy')
  return (
    <section className="card run-bar" aria-label={t('continuous.title')}>
      <h2 className="section-title">{t('continuous.title')} <span className="badge badge-neutral">{t('continuous.preview_label')}</span></h2>
      <div className="run-bar-row">
        <span>{hours ? t('simulation.operating_hours', { hours }) : t('simulation.operating_hours_unknown')}</span>
        <ClosingRule analysisId={analysisId} rule={rule} />
      </div>
      <div className="run-bar-row">
        <span className={`badge ${run.isPending ? 'badge-warn' : stored ? 'badge-ok' : 'badge-neutral'}`} role="status" data-testid="continuous-status">
          {t(run.isPending ? 'simulation.status_running' : stored ? 'simulation.status_done' : 'simulation.status_not_run')}
        </span>
        <button type="button" className="btn-primary" onClick={start} disabled={!view.compatible || run.isPending}>
          {run.isPending ? t('common.loading') : t('continuous.run')}
        </button>
        {view.expected_customers_per_day !== null && <span className="form-hint">{t('continuous.expected', { customers: Math.round(view.expected_customers_per_day) })}</span>}
      </div>
      {view.service_model && blocking.length === 0 && (
        <p className="form-hint" data-testid="continuous-service">
          {t(view.service_model === 'recorded' ? 'continuous.service_recorded' : 'continuous.service_estimated')}
          {view.service_fallbacks && view.service_fallbacks.length > 0 && ` ${t('continuous.service_fallbacks', {
            list: view.service_fallbacks.map((item) => t('continuous.service_fallback_item', { period: item.period_id, source: item.uses_period_id })).join('; '),
          })}`}
        </p>
      )}
      {(view.counter_breaks ?? 0) > 0 && blocking.length === 0 && (
        <p className="form-hint" data-testid="continuous-breaks">{t('continuous.breaks_included', { breaks: view.counter_breaks })}</p>
      )}
      <details className="preview-explained">
        <summary>{t('continuous.preview_what')}</summary>
        <p>{t('continuous.preview_explained')}</p>
      </details>
      {stored && (
        <p className="form-hint">{t('continuous.stored', { repeats: stored.evidence.params.replications, seed: stored.evidence.params.seed })} · {t(`continuous.closing_short_${stored.evidence.params.closing_policy}`)}{stored.evidence.params.service_model === 'recorded' && ` · ${t('continuous.service_recorded_short')}`}</p>
      )}
      {stored && staleNotes(stored, t).map((note) => <p key={note} role="status" className="alert alert-warn">{note}</p>)}
      {blocking.length > 0 && (
        <div role="status" className="alert alert-warn" data-testid="continuous-refusal">
          <strong>{t('continuous.cannot_run')}</strong>
          <ReasonList reasons={blocking} />
          {blocking.some((reason) => reason.code === 'no_selected_plan') && <Link to={`/analyses/${analysisId}/plans`}>{t('nav.suggested_plans')}</Link>}
        </div>
      )}
      <details className="run-advanced">
        <summary>{t('simulation.advanced')}</summary>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="continuous-repeats">{t('continuous.repeats')}</label>
            <input id="continuous-repeats" type="number" min={1} max={max} step={1} value={repeats} onChange={(event) => setRepeats(event.target.value)} />
            <p className="form-hint">{t('continuous.repeats_hint', { max, default: compatibility.default_replications })}</p>
          </div>
          <div className="form-field">
            <label htmlFor="continuous-seed">{t('continuous.seed')}</label>
            <input id="continuous-seed" type="number" min={0} step={1} value={seed} onChange={(event) => setSeed(event.target.value)} />
          </div>
        </div>
      </details>
      {error && <div role="alert" className="alert alert-error">{error}</div>}
    </section>
  )
}

function Card({ label, now, plan }: { label: string; now: string; plan: string }) {
  const { t } = useTranslation()
  return (
    <section className="card key-result" aria-label={label}>
      <h3 className="kpi-label">{label}</h3>
      <p className="headline-pair"><span>{t('simulation.run_current')}: <strong>{now}</strong></span><span aria-hidden="true">→</span><span>{t('simulation.run_suggested')}: <strong>{plan}</strong></span></p>
    </section>
  )
}

/** Four headline cards Current → Suggested from the stored runs' own summaries (no browser totals). */
function ContinuousCards({ current, suggested }: { current: ContinuousRunOut | null; suggested: ContinuousRunOut | null }) {
  const { t } = useTranslation()
  const notRun = t('simulation.status_not_run')
  const unavailable = t('results.unavailable')
  const minutes = (value: number) => `${fmtDecimal(value, 1)} ${t('results.min')}`
  const count = (value: number) => fmtDecimal(value, 1)
  const wait = (run: ContinuousRunOut | null) => {
    if (!run) return notRun
    const summary = run.evidence.result.summary.waiting_time
    const value = summary.customer_weighted_mean_hours.value
    if (value === null) return unavailable
    const spread = summary.mean_of_replication_means_hours
    return spread.min !== null && spread.max !== null && spread.min !== spread.max
      ? `${minutes(value * 60)} (${minutes(spread.min * 60)}–${minutes(spread.max * 60)})` : minutes(value * 60)
  }
  const metric = (run: ContinuousRunOut | null, pick: (out: ContinuousRunOut) => Parameters<typeof rangeText>[0]) => (
    run ? rangeText(pick(run), count) ?? unavailable : notRun
  )
  const repeats = [current, suggested].filter((run): run is ContinuousRunOut => run !== null).map((run) => run.evidence.params.replications)
  return (
    <>
      <div className="key-results" role="group" aria-label={t('continuous.key_results')}>
        <Card label={t('simulation.average_wait')} now={wait(current)} plan={wait(suggested)} />
        <Card label={t('simulation.longest_line')} now={metric(current, (run) => run.evidence.result.summary.metrics.max_queue_in_horizon)} plan={metric(suggested, (run) => run.evidence.result.summary.metrics.max_queue_in_horizon)} />
        <Card label={t('simulation.served_customers')} now={metric(current, (run) => run.evidence.result.summary.customers.per_replication.served)} plan={metric(suggested, (run) => run.evidence.result.summary.customers.per_replication.served)} />
        <Card label={t('continuous.not_served')} now={metric(current, (run) => run.evidence.result.summary.customers.per_replication.unserved)} plan={metric(suggested, (run) => run.evidence.result.summary.customers.per_replication.unserved)} />
      </div>
      {repeats.length > 0 && <p className="form-hint">{t('continuous.cards_note', { counts: [...new Set(repeats)].join(' / ') })}</p>}
    </>
  )
}

function DayCharts({ playback, startMinute, day, days }: { playback: ContinuousPlayback; startMinute: number; day: number; days: number }) {
  const { t } = useTranslation()
  const steps = waitingSteps(playback.playback.events)
  const end = Math.max(playback.playback.closing.closing_hours, steps.at(-1)?.hours ?? 0)
  const max = Math.max(1, ...steps.map((step) => step.waiting))
  const x = (hours: number) => (end > 0 ? (hours / end) * 600 : 0)
  const y = (waiting: number) => 160 - (waiting / max) * 150
  const path = steps.map((step, index) => `${index === 0 ? 'M' : 'L'}${x(step.hours)},${index === 0 ? y(step.waiting) : y(steps[index - 1].waiting)} L${x(step.hours)},${y(step.waiting)}`).join(' ')
  const peak = Math.max(0, ...steps.map((step) => step.waiting))
  const longestWait = Math.max(0, ...playback.by_period.map((period) => period.mean_wait_hours ?? 0))
  return (
    <>
      <p className="form-hint">{t('continuous.chart_day', { day: day + 1, total: days })}</p>
      <div className="grid g2">
        <section className="card" aria-labelledby="continuous-waiting-title">
          <h2 id="continuous-waiting-title" className="section-title">{t('continuous.chart_waiting')}</h2>
          <svg className="waiting-chart" viewBox="0 0 600 160" role="img" aria-label={t('continuous.chart_waiting_summary', { max: peak })} preserveAspectRatio="none">
            <line className="waiting-chart-close" x1={x(playback.playback.closing.closing_hours)} x2={x(playback.playback.closing.closing_hours)} y1={0} y2={160} />
            <path className="waiting-chart-line" fill="none" d={path} />
          </svg>
          <p className="form-hint">{t('continuous.chart_waiting_axis', { start: clockAt(startMinute, 0), end: clockAt(startMinute, end), max: peak })}</p>
        </section>
        <section className="card" aria-labelledby="continuous-period-title">
          <h2 id="continuous-period-title" className="section-title">{t('simulation.chart_wait_by_period')}</h2>
          <div className="hbar-chart" role="img" aria-labelledby="continuous-period-title">
            {playback.by_period.map((period) => (
              <div className="hbar-row" key={period.period_id}>
                <div className="hbar-head">
                  <span className="hbar-label">{period.period_id}</span>
                  <span className="hbar-value">{period.mean_wait_hours === null ? t('results.unavailable') : `${fmtDecimal(period.mean_wait_hours * 60, 1)} ${t('results.min')}`}</span>
                </div>
                <span className="hbar-track"><span className="hbar-fill" style={{ width: `${longestWait > 0 && period.mean_wait_hours !== null ? (period.mean_wait_hours / longestWait) * 100 : 0}%` }} /></span>
              </div>
            ))}
          </div>
          <p className="form-hint">{t('continuous.by_period_hint')}</p>
        </section>
      </div>
    </>
  )
}

function useDayPlayback(analysisId: number, run: ContinuousRunOut | null, day: number) {
  return useQuery({
    queryKey: ['continuous-playback', analysisId, run?.evidence.id, day],
    queryFn: () => getContinuousPlayback(analysisId, (run as ContinuousRunOut).evidence.id, day),
    enabled: run !== null,
    staleTime: Infinity,
  })
}

function DayPicker({ days, day, onChange }: { days: number; day: number; onChange: (day: number) => void }) {
  const { t } = useTranslation()
  if (days <= 1) return null
  return (
    <div className="form-field inline-field">
      <label htmlFor="continuous-day">{t('continuous.replay_day')}</label>
      <select id="continuous-day" value={day} onChange={(event) => onChange(Number(event.target.value))}>
        {Array.from({ length: days }, (_, index) => <option key={index} value={index}>{t('continuous.day_option', { day: index + 1, total: days })}</option>)}
      </select>
    </div>
  )
}

/** The day picker and the two charts of one repeated day of the shown run (keyed by run, so day resets). */
function ShownDay({ analysisId, shown }: { analysisId: number; shown: ContinuousRunOut }) {
  const { t } = useTranslation()
  const [day, setDay] = useState(0)
  const playback = useDayPlayback(analysisId, shown, day)
  return (
    <>
      {!shown.evidence.result.summary.customers.conserved_in_every_replication && (
        <div role="alert" className="alert alert-error">{t('continuous.not_conserved')}</div>
      )}
      <DayPicker days={shown.evidence.params.replications} day={day} onChange={setDay} />
      {playback.isError && <div role="alert" className="alert alert-error">{requestError(playback.error, t('errors.server'))}</div>}
      {playback.data && (
        <DayCharts playback={playback.data} startMinute={shown.evidence.result.provenance.inputs.horizon.start_minute} day={day} days={shown.evidence.params.replications} />
      )}
      {playback.data && (
        <details className="card collapsible-card">
          <summary><h2 className="section-title">{t('simulation.more_results')}</h2></summary>
          <div className="table-scroll" role="region" aria-label={t('continuous.period_table', { day: day + 1 })} tabIndex={0}>
            <table>
              <caption>{t('continuous.period_table', { day: day + 1 })}</caption>
              <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('simulation.arrived')}</th><th scope="col">{t('simulation.served_customers')}</th><th scope="col">{t('continuous.not_served')}</th><th scope="col">{t('simulation.average_wait')}</th></tr></thead>
              <tbody>{playback.data.by_period.map((period) => (
                <tr key={period.period_id}>
                  <th scope="row">{period.period_id}</th><td>{period.arrivals}</td><td>{period.served}</td><td>{period.unserved}</td>
                  <td>{period.mean_wait_hours === null ? t('results.unavailable') : `${fmtDecimal(period.mean_wait_hours * 60, 1)} ${t('results.min')}`}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      )}
    </>
  )
}

function ContinuousResults({ analysisId, shown, current, suggested }: {
  analysisId: number
  shown: ContinuousRunOut | null
  current: ContinuousRunOut | null
  suggested: ContinuousRunOut | null
}) {
  return (
    <div className="page-stack">
      <ContinuousCards current={current} suggested={suggested} />
      {shown && <ShownDay key={shown.evidence.id} analysisId={analysisId} shown={shown} />}
    </div>
  )
}

function ContinuousReplay({ analysisId, shown }: { analysisId: number; shown: ContinuousRunOut | null }) {
  const { t } = useTranslation()
  const [day, setDay] = useState(0)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [goTo, setGoTo] = useState('')
  const [goError, setGoError] = useState<string | null>(null)
  const playback = useDayPlayback(analysisId, shown, day)
  const events = useMemo(() => playback.data?.playback.events ?? [], [playback.data])
  const end = events.at(-1)?.t ?? 0
  const startMinute = shown?.evidence.result.provenance.inputs.horizon.start_minute ?? 0

  useEffect(() => {
    if (!playing || end <= 0) return undefined
    const step = (end / SECONDS_AT_1X) * speed * 0.1
    const timer = window.setInterval(() => setTime((value) => {
      const next = Math.min(end, value + step)
      if (next >= end) setPlaying(false)
      return next
    }), 100)
    return () => window.clearInterval(timer)
  }, [playing, speed, end])

  if (!shown) return <p className="empty-state">{t('simulation.run_first')}</p>
  const state = stateAt(events, time)
  const hasBreaks = events.some((event) => event.type === 'break_due')
  const go = () => {
    const hours = hoursAt(startMinute, goTo)
    if (hours === null || hours > end) return setGoError(t('continuous.goto_error', { start: clockAt(startMinute, 0), end: clockAt(startMinute, end) }))
    setGoError(null)
    setTime(hours)
  }
  return (
    <section className="card" aria-label={t('continuous.replay_title')}>
      <h2 className="section-title">{t('continuous.replay_title')} <span className="badge badge-neutral">{t('continuous.preview_label')}</span></h2>
      <DayPicker days={shown.evidence.params.replications} day={day} onChange={(value) => { setDay(value); setTime(0); setPlaying(false) }} />
      {playback.isLoading && <p className="form-hint">{t('common.loading')}</p>}
      {playback.isError && <div role="alert" className="alert alert-error">{requestError(playback.error, t('errors.server'))}</div>}
      {playback.data && (
        <>
          <p className="replay-clock" data-testid="continuous-clock">{t('simulation.replay_clock')}: <strong>{clockAt(startMinute, time)}</strong></p>
          <div className="live-kpis" data-testid="continuous-state">
            <span>{t('continuous.state_waiting')}: <strong>{state.waiting}</strong></span>
            <span>{t('continuous.state_serving')}: <strong>{state.serving}</strong></span>
            <span>{t('continuous.state_idle')}: <strong>{state.idle}</strong></span>
            <span>{t('continuous.state_draining')}: <strong>{state.draining}</strong></span>
            {hasBreaks && <span>{t('continuous.state_on_break')}: <strong>{state.onBreak}</strong></span>}
            {hasBreaks && <span>{t('continuous.state_breaks_waiting')}: <strong>{state.breaksWaiting}</strong></span>}
            <span>{t('continuous.state_arrived')}: <strong>{state.arrived}</strong></span>
            <span>{t('continuous.state_served')}: <strong>{state.served}</strong></span>
            <span>{t('continuous.state_unserved')}: <strong>{state.unserved}</strong></span>
          </div>
          {time >= playback.data.playback.closing.closing_hours && <p className="form-hint">{t('continuous.after_closing')}</p>}
          <div className="playback-controls live-controls">
            <button type="button" className="btn-secondary" onClick={() => { setTime(0); setPlaying(false) }}>{t('simulation.playback_restart')}</button>
            <button type="button" className="btn-primary" onClick={() => setPlaying((value) => !value)}>{playing ? t('simulation.playback_pause') : t('simulation.playback_play')}</button>
            <input type="range" aria-label={t('continuous.replay_position')} min={0} max={end} step={end / 500 || 0.01} value={time} onChange={(event) => { setTime(Number(event.target.value)); setPlaying(false) }} />
            <label className="inline-field">{t('simulation.playback_speed')}
              <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
                {SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}
              </select>
            </label>
            <span className="replay-goto">
              <label htmlFor="continuous-goto">{t('simulation.replay_go_to')}</label>
              <input id="continuous-goto" type="time" value={goTo} onChange={(event) => setGoTo(event.target.value)} />
              <button type="button" className="btn-secondary" onClick={go}>{t('simulation.replay_go')}</button>
            </span>
          </div>
          {goError && <p role="alert" className="form-hint">{goError}</p>}
          <p className="form-hint">{t('continuous.replay_source')}</p>
        </>
      )}
    </section>
  )
}

function ContinuousChecks({ shown }: { shown: ContinuousRunOut | null }) {
  const { t } = useTranslation()
  const count = (value: number) => fmtDecimal(value, 1)
  const rows: Array<[string, string | null]> = shown ? [
    [t('simulation.average_wait'), rangeText(shown.evidence.result.summary.waiting_time.mean_of_replication_means_hours, (value) => `${fmtDecimal(value, 1)} ${t('results.min')}`, 60)],
    [t('simulation.longest_line'), rangeText(shown.evidence.result.summary.metrics.max_queue_in_horizon, count)],
    [t('simulation.served_customers'), rangeText(shown.evidence.result.summary.customers.per_replication.served, count)],
    [t('continuous.not_served'), rangeText(shown.evidence.result.summary.customers.per_replication.unserved, count)],
    [t('continuous.utilization'), rangeText(shown.evidence.result.summary.metrics.utilization_in_horizon, (value) => `${fmtDecimal(value, 1)}%`, 100)],
  ] : []
  return (
    <section className="card" aria-label={t('continuous.checks_title')}>
      <h2 className="section-title">{t('continuous.checks_title')}</h2>
      <p role="status" className="alert alert-warn" data-testid="continuous-no-decision">{t('continuous.no_decision')}</p>
      {shown ? (
        <div className="table-scroll" role="region" aria-label={t('continuous.ranges_title')} tabIndex={0}>
          <table>
            <caption>{t('continuous.ranges_title')}</caption>
            <tbody>{rows.map(([label, value]) => <tr key={label}><th scope="row">{label}</th><td>{value ?? t('results.unavailable')}</td></tr>)}</tbody>
          </table>
        </div>
      ) : <p className="empty-state">{t('simulation.run_first')}</p>}
    </section>
  )
}

/** B4a: the full-day shared-line run (preview) on each Queue simulation page (spec section 6). */
export function ContinuousSection({ analysisId, run, page }: { analysisId: number; run: ContinuousPlan; page: SimulationPageName }) {
  const { t } = useTranslation()
  const { closing, compatibility, current, suggested } = useContinuous(analysisId)
  if (closing.isLoading || compatibility.isLoading) return <p className="form-hint">{t('common.loading')}</p>
  if (!compatibility.data || !closing.data) {
    return <div role="alert" className="alert alert-error">{requestError(compatibility.error ?? closing.error, t('errors.server'))}</div>
  }
  const shown = run === 'suggested' ? suggested : current
  return (
    <div className="page-stack continuous-section">
      <ContinuousRunBar key={`continuous-${run}`} analysisId={analysisId} plan={run} compatibility={compatibility.data} rule={closing.data.closing_policy} stored={shown} />
      {page === 'results' && <ContinuousResults analysisId={analysisId} shown={shown} current={current} suggested={suggested} />}
      {page === 'replay' && <ContinuousReplay key={`replay-${shown?.evidence.id}`} analysisId={analysisId} shown={shown} />}
      {page === 'checks' && <ContinuousChecks shown={shown} />}
    </div>
  )
}
