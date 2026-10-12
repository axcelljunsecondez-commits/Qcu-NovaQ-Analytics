import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { runAnalysis, runGuestCalculator, type AnalysisModel } from '../api/analysis'
import type { AnalysisOut } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { InfoTip } from '../components/ui/InfoTip'
import { fmtDecimal, fmtPctDecimal } from '../lib/format'
import {
  SITUATIONS,
  inputProblems,
  modelFor,
  neighbourCounters,
  requestFor,
  summarize,
  type CalculatorInputs,
  type CalculatorSummary,
  type Situation,
} from '../lib/quickCalculator'
import { requestError } from '../lib/simulationEvidence'

type FieldKey = 'lambda' | 'mu' | 'c' | 'spread' | 'capacity' | 'patience'

const FIELDS: Record<Situation, FieldKey[]> = {
  basic: ['lambda', 'mu', 'c'],
  variable: ['lambda', 'mu', 'c', 'spread'],
  limited: ['lambda', 'mu', 'c', 'capacity', 'spread'],
  leaving: ['lambda', 'mu', 'c', 'patience'],
}

interface Outcome {
  model: AnalysisModel
  counters: number
  summary: CalculatorSummary
  error: string | null
}

interface Calculation {
  situation: Situation
  main: Outcome
  fewer: Outcome | null
  more: Outcome | null
}

function numberOrNull(value: string): number | null {
  return value.trim() === '' ? null : Number(value)
}

// Quick calculator (spec 2026-10-09 §7.12, plan U9 + B2). Guests (/calculator) use the public endpoint
// and signed-in users (/tools/calculator) the account endpoint; both return the same numbers.
export function QuickCalculatorPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const requested = params.get('situation')
  const situation: Situation = (SITUATIONS as readonly string[]).includes(requested ?? '') ? requested as Situation : 'basic'
  const [values, setValues] = useState<Record<FieldKey, string>>({ lambda: '', mu: '', c: '', spread: '', capacity: '', patience: '' })
  const [problems, setProblems] = useState<FieldKey[]>([])
  const [calculation, setCalculation] = useState<Calculation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const run = user ? runAnalysis : runGuestCalculator
  const startPath = user ? '/analyses/new' : `/login?next=${encodeURIComponent('/analyses/new')}`

  function chooseSituation(next: Situation) {
    const nextParams = new URLSearchParams(params)
    nextParams.set('situation', next)
    setParams(nextParams, { replace: true })
    setCalculation(null)
    setProblems([])
    setError(null)
  }

  async function calculate(event: FormEvent) {
    event.preventDefault()
    const inputs: CalculatorInputs = {
      lambda: Number(values.lambda), mu: Number(values.mu), c: Number(values.c),
      spreadMinutes: numberOrNull(values.spread), capacity: numberOrNull(values.capacity),
      patienceMinutes: numberOrNull(values.patience),
    }
    const found = inputProblems(situation, inputs)
      .map((problem) => problem as FieldKey)
      .concat(FIELDS[situation].filter((field) => ['lambda', 'mu', 'c'].includes(field) && values[field].trim() === ''))
    setProblems([...new Set(found)])
    if (found.length > 0) return
    const { fewer, more } = neighbourCounters(situation, inputs)
    async function outcome(counters: number): Promise<Outcome> {
      const model = modelFor(situation, inputs, counters)
      const result: AnalysisOut = await run(model, requestFor(situation, inputs, counters))
      return { model, counters, summary: summarize(situation, result), error: result.error }
    }
    setRunning(true)
    setError(null)
    try {
      const [main, fewerOutcome, moreOutcome] = await Promise.all([
        outcome(inputs.c),
        fewer === null ? Promise.resolve(null) : outcome(fewer),
        more === null ? Promise.resolve(null) : outcome(more),
      ])
      setCalculation({ situation, main, fewer: fewerOutcome, more: moreOutcome })
    } catch (failure) {
      setCalculation(null)
      setError(requestError(failure, t('errors.server')))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="page-stack quick-calculator">
      <header className="page-header">
        <p className="topbar-eyebrow">{t('calculator.eyebrow')}</p>
        <h1 className="page-title">{t('calculator.title')}</h1>
        <p className="page-caption">{t('calculator.note')} <Link to={startPath}>{t('calculator.start')}</Link></p>
      </header>

      <div className="tabs" role="tablist" aria-label={t('calculator.situations')}>
        {SITUATIONS.map((item) => (
          <button key={item} type="button" role="tab" id={`calculator-tab-${item}`} aria-selected={item === situation}
            aria-controls="calculator-panel" className={`tab${item === situation ? ' active' : ''}`} onClick={() => chooseSituation(item)}>
            {t(`calculator.situation.${item}`)}
          </button>
        ))}
      </div>

      <form className="card" id="calculator-panel" role="tabpanel" aria-labelledby={`calculator-tab-${situation}`} onSubmit={(event) => void calculate(event)} noValidate>
        <p className="form-hint">{t(`calculator.situation_help.${situation}`)}</p>
        <div className="form-row">
          {FIELDS[situation].map((field) => {
            const label = t(`calculator.field.${field}${field === 'spread' && situation === 'limited' ? '_optional' : ''}`)
            return (
              <div className="form-field" key={field}>
                <label htmlFor={`calculator-${field}`}>{label}</label>
                <InfoTip name={label} text={t(`calculator.field_info.${field}`)} />
                <input id={`calculator-${field}`} type="number" inputMode="decimal" min={field === 'c' || field === 'capacity' ? 1 : 0}
                  step={field === 'c' || field === 'capacity' ? 1 : 'any'} value={values[field]} aria-invalid={problems.includes(field)}
                  aria-describedby={problems.includes(field) ? `calculator-${field}-error` : undefined}
                  onChange={(event) => setValues((old) => ({ ...old, [field]: event.target.value }))} />
                {problems.includes(field) && <span id={`calculator-${field}-error`} className="field-error">{t(`calculator.field_error.${field}`)}</span>}
              </div>
            )
          })}
        </div>
        <button type="submit" className="btn-primary" disabled={running}>{running ? t('common.loading') : t('calculator.calculate')}</button>
        {error && <div role="alert" className="alert alert-error">{error}</div>}
      </form>

      {calculation && <Results calculation={calculation} />}
    </div>
  )
}

function Results({ calculation }: { calculation: Calculation }) {
  const { t } = useTranslation()
  const { situation, main } = calculation
  const s = main.summary
  const cards: Array<{ key: string; value: string }> = [
    { key: 'wait', value: s.waitMinutes === null ? '—' : t('calculator.minutes', { value: fmtDecimal(s.waitMinutes) }) },
    { key: 'busy', value: fmtPctDecimal(s.busy) },
    { key: 'waiting', value: fmtDecimal(s.waiting) },
  ]
  if (s.keepUp !== null) cards.push({ key: 'keep_up', value: t(`calculator.keep_up.${s.keepUp}`) })
  if (situation === 'limited') cards.push({ key: 'turned_away', value: fmtPctDecimal(s.turnedAway) })
  if (situation === 'leaving') cards.push({ key: 'leaving', value: fmtPctDecimal(s.leaving) })
  return (
    <section className="card" aria-label={t('calculator.results')}>
      <h2 className="card-title">{t('calculator.results')}</h2>
      <p className="form-hint">{t('calculator.model_used', { model: t(`calculator.model.${main.model}`) })}</p>
      <div className="card-grid">
        {cards.map((card) => (
          <div className="card kpi-card" key={card.key} data-testid={`calculator-${card.key}`}>
            <span className="kpi-label">{t(`calculator.result.${card.key}`)} <InfoTip name={t(`calculator.result.${card.key}`)} text={t(`calculator.result_info.${card.key}`)} /></span>
            <strong className="kpi-value">{card.value}</strong>
          </div>
        ))}
      </div>
      <h3 className="card-title">{t('calculator.what_this_means')}</h3>
      <ul className="calculator-meaning" data-testid="calculator-meaning">
        <li>{meaning(t, situation, main)}</li>
        {calculation.fewer && <li>{meaning(t, situation, calculation.fewer)}</li>}
        {calculation.more && <li>{meaning(t, situation, calculation.more)}</li>}
      </ul>
    </section>
  )
}

/** One sentence built only from the returned fields; no advice. */
function meaning(t: (key: string, options?: Record<string, unknown>) => string, situation: Situation, outcome: Outcome): string {
  const s = outcome.summary
  const counters = outcome.counters
  if (s.keepUp === 'no') return t('calculator.meaning.cannot_keep_up', { counters })
  if (s.waitMinutes === null || s.busy === null) {
    return t('calculator.meaning.not_calculated', { counters })
  }
  const base = t('calculator.meaning.result', { counters, wait: fmtDecimal(s.waitMinutes), busy: fmtPctDecimal(s.busy) })
  if (situation === 'limited') return `${base} ${t('calculator.meaning.turned_away', { share: fmtPctDecimal(s.turnedAway) })}`
  if (situation === 'leaving') return `${base} ${t('calculator.meaning.leaving', { share: fmtPctDecimal(s.leaving) })}`
  return base
}
