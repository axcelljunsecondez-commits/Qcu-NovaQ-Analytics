import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { selectPlaybackLayout } from '../../lib/simulationPlayback'
import { dayOrigin, inactiveQueueIdsAt, mergeDayTrace, operatingHours, runTimeFor, scheduledBreaks, wallClock } from '../../lib/replay'
import { LiveSimulationPlayback } from '../simulation/LiveSimulationPlayback'
import { SeparateSimulationPlayback } from '../simulation/SeparateSimulationPlayback'
import { currentRun, suggestedRun, type RunChoice, type SimulationContext } from './simulationContext'

/** Replay (D28): the chosen run's own events. One continuous day plays as one day; other runs one period at a time. */
export function ReplayView({ context, run }: { context: SimulationContext; run: RunChoice }) {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [periodTime, setPeriodTime] = useState<string | null>(null)
  const origin = dayOrigin(context.analysis.queue_setup)
  const breaks = context.separate ? scheduledBreaks(context.analysis.queue_setup) : []
  const suggested = run === 'suggested' ? suggestedRun(context) : null
  const current = run === 'current' ? currentRun(context) : null

  if (!suggested && !current) return <p className="empty-state">{t('simulation.run_first')}</p>

  if (suggested?.kind === 'separate') {
    const day = context.representativeDay ? mergeDayTrace(suggested.result.periods) : null
    if (day) {
      const requested = origin === null ? null : runTimeFor(origin, params.get('t') ?? '')
      return (
        <SeparateSimulationPlayback
          trace={day}
          periodLabel={operatingHours(context.analysis.queue_setup)}
          originMinutes={origin}
          scheduled={breaks}
          inactiveQueueIds={(hours) => inactiveQueueIdsAt(suggested.result.periods, hours)}
          initialTime={requested !== null && requested <= day.total_hours ? requested : 0}
          onTimeChange={(hours) => {
            if (origin === null) return
            const next = new URLSearchParams(params)
            next.set('t', wallClock(origin, hours))
            setParams(next, { replace: true })
          }}
        />
      )
    }
    const periods = suggested.result.periods
    const active = periods.find((period) => period.time === periodTime) ?? periods[0]
    return (
      <div className="page-stack">
        <div className="alert alert-info" role="status">{t('simulation.one_period_notice')}</div>
        <div className="period-picker" role="group" aria-label={t('simulation.sep_period')}>
          {periods.map((period) => (
            <button key={period.time} type="button" aria-pressed={active?.time === period.time} onClick={() => setPeriodTime(period.time)}>{period.time}</button>
          ))}
        </div>
        {active && <SeparateSimulationPlayback key={active.time} trace={active.trace} inactiveQueueIds={active.inactive_queue_ids} scheduled={breaks} />}
      </div>
    )
  }

  const trace = suggested?.result ?? current
  if (!trace) return <p className="empty-state">{t('simulation.run_first')}</p>
  const segment = trace.segments.find((item) => item.simulation_supported && !item.error) ?? trace.segments[0]
  const layout = segment ? selectPlaybackLayout(segment.queue_structure) : (context.separate ? 'separate' : 'shared')
  return (
    <div className="page-stack">
      <div className="alert alert-info" role="status">{t('simulation.one_period_notice')}</div>
      <p className="form-hint"><span className="badge badge-neutral">{t(layout === 'separate' ? 'simulation.playback_view_separate' : 'simulation.playback_view_shared')}</span></p>
      {layout === 'separate' ? <SeparateSimulationPlayback trace={trace} /> : <LiveSimulationPlayback trace={trace} />}
    </div>
  )
}
