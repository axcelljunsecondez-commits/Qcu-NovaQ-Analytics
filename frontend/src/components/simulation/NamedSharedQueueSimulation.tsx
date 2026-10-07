import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listAnalysisDatasets } from '../../api/analyses'
import {
  createNamedRun,
  getNamedContract,
  getNamedReplication,
  getNamedRun,
  listNamedRuns,
  namedApiError,
  validateNamedInputs,
  type NamedApiError,
  type NamedContract,
  type NamedValidateOut,
} from '../../api/sharedNamed'
import { ApiState } from '../ui/ApiState'
import { fmtDecimal } from '../../lib/format'
import {
  buildRequest,
  emptyForm,
  formFingerprint,
  formFromRun,
  limitProblems,
  minutesToClock,
  type FieldError,
  type LimitProblem,
  type NamedForm,
} from '../../lib/namedWorkforce'
import { NamedAttributionTables } from './NamedAttributionTables'
import { NamedReplicationTable } from './NamedReplicationTable'
import { NamedSharedQueuePlayback } from './NamedSharedQueuePlayback'
import { NamedWorkforceForm } from './NamedWorkforceForm'

interface Props {
  analysisId: number
  modeSwitch: ReactNode
}

const WHOLE = /^\d+$/

function wholeIn(text: string, min: number, max: number): number | null {
  const trimmed = text.trim()
  if (!WHOLE.test(trimmed)) return null
  const value = Number(trimmed)
  return Number.isSafeInteger(value) && value >= min && value <= max ? value : null
}

function approvedPolicy(contract: NamedContract): Record<string, string> {
  return Object.fromEntries(Object.entries(contract.employee_policy).map(([name, item]) => [name, item.approved]))
}

/** A refusal shown exactly as the API reported it; a code the UI does not know falls back to a generic message. */
function RequestError({ error }: { error: NamedApiError }) {
  const { t } = useTranslation()
  const detail = (error.detail && typeof error.detail === 'object' && !Array.isArray(error.detail)
    ? error.detail : {}) as Record<string, unknown>
  const list = (value: unknown) => (Array.isArray(value) ? value : [])
  if (error.code === 'persistence_identity_mismatch') {
    return (
      <div role="alert" className="alert alert-error" data-testid="named-error-persistence">
        <p>{t('simulation.named_error_persistence_identity_mismatch')}</p>
        <ul>
          {list(detail.checks).map((check, index) => {
            const item = check as { check?: string; message?: string }
            return <li key={`check-${index}`}><code>{item.check}</code>: {item.message}</li>
          })}
        </ul>
      </div>
    )
  }
  if (error.code === 'regeneration_identity' || error.code === 'playback_check_failed' || error.code === 'attribution_check_failed') {
    return (
      <div role="alert" className="alert alert-error" data-testid="named-error-regeneration">
        <p>{t(`simulation.named_error_${error.code}`)}</p>
        <p><code>{error.code}</code> · <code>{String(detail.check ?? '—')}</code></p>
        {typeof detail.message === 'string' && <p>{detail.message}</p>}
      </div>
    )
  }
  if (error.code === 'named_input_invalid') {
    return (
      <div role="alert" className="alert alert-error" data-testid="named-error-input">
        <p>{t('simulation.named_error_named_input_invalid', { stage: t(`simulation.named_stage_${String(detail.stage)}`) })}</p>
        <ul>{list(detail.problems).map((problem, index) => <li key={`p-${index}`}>{String(problem)}</li>)}</ul>
      </div>
    )
  }
  if (error.code === 'limit_exceeded' && detail.limit === 'expected_customers') {
    return (
      <div role="alert" className="alert alert-error" data-testid="named-error-customer-bound">
        {t('simulation.named_customer_bound_exceeded', {
          value: String(detail.value ?? ''), max: String(detail.max ?? ''), replications: String(detail.max_replications ?? ''),
        })}
      </div>
    )
  }
  const known = ['limit_exceeded', 'ineligible_setup', 'analysis_archived', 'dataset_not_found', 'dataset_not_processed',
    'evidence_too_large', 'result_not_serializable', 'run_not_found', 'replication_not_found']
  const key = error.code && known.includes(error.code)
    ? `simulation.named_error_${error.code}`
    : (error.status === 422 ? 'simulation.named_error_schema' : 'errors.server')
  return (
    <div role="alert" className="alert alert-error" data-testid="named-error">
      {t(key, {
        limit: String(detail.limit ?? ''), value: String(detail.value ?? ''), max: String(detail.max ?? ''),
        bytes: String(detail.bytes ?? ''), max_bytes: String(detail.max_bytes ?? ''),
        reasons: list(detail.reasons).map(String).join(', '),
      })}
    </div>
  )
}

function ValidationResult({ result }: { result: NamedValidateOut }) {
  const { t } = useTranslation()
  const report = result.roster_report
  return (
    <section className="card" data-testid="named-validation" aria-label={t('simulation.named_validation_title')}>
      <h3 className="section-title">{t('simulation.named_validation_title')}</h3>
      <p>
        <span className={`badge ${result.runnable ? 'badge-ok' : 'badge-bad'}`} data-testid="named-runnable">
          {t(result.runnable ? 'simulation.named_runnable' : 'simulation.named_not_runnable')}
        </span>
      </p>
      {result.stage_failed && (
        <div role="alert" className="alert alert-error">
          <p>{t('simulation.named_stage_failed', { stage: t(`simulation.named_stage_${result.stage_failed}`) })}</p>
          <ul>{result.problems.map((problem, index) => <li key={`problem-${index}`}>{problem}</li>)}</ul>
        </div>
      )}
      {result.demand && (
        <div className="table-scroll">
          <table>
            <caption>{t('simulation.named_demand_caption', { dataset: result.demand.dataset_id })}</caption>
            <thead>
              <tr>
                <th scope="col">{t('simulation.named_col_period')}</th>
                <th scope="col">{t('simulation.named_col_lambda')}</th>
                <th scope="col">{t('simulation.named_col_mu')}</th>
              </tr>
            </thead>
            <tbody>
              {result.demand.demand_periods.map((period) => (
                <tr key={period.period_id}>
                  <th scope="row">{minutesToClock(period.start_minute)}–{minutesToClock(period.end_minute)}</th>
                  <td>{fmtDecimal(period.arrival_rate_per_hour)}</td>
                  <td>{fmtDecimal(period.service_rate_per_hour)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {report && (
        <div data-testid="named-roster-report">
          <h4>{t('simulation.named_roster_report_title', { status: report.status })}</h4>
          {report.violations.length > 0 && (
            <ul>{report.violations.map((item, index) => <li key={`v-${index}`}><code>{item.code}</code>: {item.message}</li>)}</ul>
          )}
          {report.missing.length > 0 && (
            <ul>
              {report.missing.map((item, index) => (
                <li key={`m-${index}`}>{t('simulation.named_missing_field', { employee: item.employee_id ?? '—', field: item.field })} — {item.consequence}</li>
              ))}
            </ul>
          )}
          {report.totals && (
            <p className="form-hint">
              {t('simulation.named_scheduled_minutes', {
                employee: report.totals.minutes.scheduled_employee_minutes ?? '—',
                active: report.totals.minutes.scheduled_active_server_minutes ?? '—',
                breaks: report.totals.minutes.break_minutes ?? '—',
              })}
            </p>
          )}
          {report.register_check && (
            <p className="form-hint">
              {t('simulation.named_register_check', {
                registers: report.register_check.register_count,
                max: report.register_check.max_active_servers,
              })}
            </p>
          )}
          {report.coverage && (
            <p className="form-hint">
              {t('simulation.named_coverage', {
                shortfall: report.coverage.shortfall_server_minutes,
                surplus: report.coverage.surplus_server_minutes,
              })}{' '}{report.coverage.note}
            </p>
          )}
        </div>
      )}
    </section>
  )
}

export function NamedSharedQueueSimulation({ analysisId, modeSwitch }: Props) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<NamedForm>(emptyForm)
  const [clientErrors, setClientErrors] = useState<FieldError[]>([])
  const [limitErrors, setLimitErrors] = useState<LimitProblem[]>([])
  const [validated, setValidated] = useState<{ fingerprint: string; result: NamedValidateOut } | null>(null)
  const [replications, setReplications] = useState('')
  const [seed, setSeed] = useState('')
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [selectedReplication, setSelectedReplication] = useState<number | null>(null)

  const contract = useQuery({ queryKey: ['shared-named', 'contract', analysisId], queryFn: () => getNamedContract(analysisId) })
  const datasets = useQuery({ queryKey: ['shared-named', 'datasets', analysisId], queryFn: () => listAnalysisDatasets(analysisId) })
  const runs = useQuery({ queryKey: ['shared-named', 'runs', analysisId], queryFn: () => listNamedRuns(analysisId) })
  const runDetail = useQuery({
    queryKey: ['shared-named', 'run', analysisId, selectedRunId],
    queryFn: () => getNamedRun(analysisId, selectedRunId as number),
    enabled: selectedRunId !== null,
  })
  const replication = useQuery({
    queryKey: ['shared-named', 'replication', analysisId, selectedRunId, selectedReplication],
    queryFn: () => getNamedReplication(analysisId, selectedRunId as number, selectedReplication as number),
    enabled: selectedRunId !== null && selectedReplication !== null,
    retry: false,
    staleTime: Infinity,
  })
  const validate = useMutation({
    mutationFn: ({ body }: { fingerprint: string; body: ReturnType<typeof buildRequest> & { ok: true } }) =>
      validateNamedInputs(analysisId, body.body),
    onSuccess: (result, variables) => setValidated({ fingerprint: variables.fingerprint, result }),
  })
  const run = useMutation({
    mutationFn: (body: Parameters<typeof createNamedRun>[1]) => createNamedRun(analysisId, body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['shared-named', 'runs', analysisId] })
      setSelectedRunId(data.evidence.id)
      setSelectedReplication(null)
    },
  })

  const header = (
    <div className="topbar">
      <div>
        <div className="topbar-eyebrow">{t('simulation.workflow_eyebrow')}</div>
        <h1 className="page-title">{t('simulation.named_title')}</h1>
        <p className="page-caption">{t('simulation.named_caption')}</p>
      </div>
    </div>
  )

  if (contract.isLoading || datasets.isLoading) {
    return <div>{header}{modeSwitch}<ApiState.Loading /></div>
  }
  if (contract.isError || !contract.data) {
    return <div>{header}{modeSwitch}<ApiState.ErrorState /></div>
  }
  const terms = contract.data
  const banner = (
    <div role="note" className="alert alert-warn" data-testid="named-banner">
      <ul>
        <li>{t('simulation.named_banner_pseudonymous')}</li>
        <li>{t('simulation.named_banner_scope')} <span className="form-hint">{terms.model_scope}</span></li>
        <li>{t('simulation.named_banner_no_verdict')} <span className="form-hint">{terms.verdict_reason}</span></li>
        <li>{t('simulation.named_banner_no_cost')}</li>
        <li>{t('simulation.named_banner_limits', { status: terms.limits.status })}</li>
      </ul>
    </div>
  )

  if (!terms.eligible) {
    return (
      <div>
        {header}
        {modeSwitch}
        {banner}
        <div role="alert" className="alert alert-error" data-testid="named-ineligible">
          <p>{t('simulation.named_ineligible')}</p>
          <ul>{terms.ineligible_reasons.map((reason) => <li key={reason}>{t(`simulation.named_reason_${reason}`)}</li>)}</ul>
        </div>
      </div>
    )
  }

  const fingerprint = formFingerprint(form)
  const policy = approvedPolicy(terms)
  const replicationCount = wholeIn(replications, 1, terms.limits.max_replications)
  const seedValue = wholeIn(seed, terms.seed.min, terms.seed.max)
  const validatedNow = validated !== null && validated.fingerprint === fingerprint
  // Spec section 22.8: expected customers per run (replications x the validated demand) may not exceed the bound.
  // The server refuses it too; this only explains the refusal before a request is sent.
  const perReplication = validatedNow && validated ? validated.result.demand?.expected_customers_per_replication ?? null : null
  const customerBound = terms.limits.max_expected_customers_per_run
  const expectedPerRun = perReplication !== null && replicationCount !== null ? perReplication * replicationCount : null
  const overCustomerBound = expectedPerRun !== null && expectedPerRun > customerBound
  const canRun = validatedNow && validated.result.runnable && replicationCount !== null && seedValue !== null
    && !overCustomerBound && !run.isPending

  function submitValidate() {
    setValidated(null)
    validate.reset()
    const built = buildRequest(form, policy)
    if (!built.ok) {
      setClientErrors(built.errors)
      setLimitErrors([])
      return
    }
    setClientErrors([])
    const limits = limitProblems(built.body, terms.limits)
    setLimitErrors(limits)
    if (limits.length === 0) validate.mutate({ fingerprint, body: built })
  }

  function submitRun() {
    const built = buildRequest(form, policy)
    if (!built.ok || replicationCount === null || seedValue === null) return
    run.mutate({ ...built.body, replications: replicationCount, seed: seedValue })
  }

  const detail = runDetail.data
  const provenance = detail?.evidence.result.provenance

  return (
    <div data-testid="named-simulation">
      {header}
      {modeSwitch}
      {banner}

      <NamedWorkforceForm form={form} onChange={setForm} contract={terms} datasets={datasets.data?.datasets ?? []}
        disabled={validate.isPending || run.isPending} />

      {clientErrors.length > 0 && (
        <div role="alert" className="alert alert-error" data-testid="named-client-errors">
          <ul>
            {clientErrors.map((item, index) => (
              <li key={`ce-${index}`}>{t(`simulation.named_field_${item.code}`, { field: item.field })}</li>
            ))}
          </ul>
        </div>
      )}
      {limitErrors.length > 0 && (
        <div role="alert" className="alert alert-error" data-testid="named-limit-errors">
          <ul>
            {limitErrors.map((item, index) => (
              <li key={`le-${index}`}>{t('simulation.named_error_limit_exceeded', { limit: item.limit, value: item.value, max: item.max })}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="form-row">
        <button type="button" className="btn-primary" disabled={validate.isPending || run.isPending} onClick={submitValidate}>
          {validate.isPending ? t('common.loading') : t('simulation.named_validate')}
        </button>
      </div>
      {validate.isError && <RequestError error={namedApiError(validate.error)} />}
      {validated && <ValidationResult result={validated.result} />}
      {validated && !validatedNow && (
        <p role="status" className="form-hint" data-testid="named-validation-stale">{t('simulation.named_validation_stale')}</p>
      )}

      <section className="card simulation-controls" aria-label={t('simulation.named_run_title')}>
        <h3 className="section-title">{t('simulation.named_run_title')}</h3>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="named-replications">{t('simulation.named_replications')}</label>
            <input id="named-replications" type="text" inputMode="numeric" value={replications}
              onChange={(event) => setReplications(event.target.value)} />
            <span className="form-hint">{t('simulation.named_replications_hint', { max: terms.limits.max_replications })}</span>
          </div>
          <div className="form-field">
            <label htmlFor="named-seed">{t('simulation.named_seed')}</label>
            <input id="named-seed" type="text" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value)} />
            <span className="form-hint">{t('simulation.named_seed_hint', { min: terms.seed.min, max: terms.seed.max })}</span>
          </div>
          <button type="button" className="btn-primary" disabled={!canRun} onClick={submitRun}>
            {run.isPending ? t('simulation.named_running') : t('simulation.named_run')}
          </button>
        </div>
        {perReplication !== null && (
          <p className="form-hint" data-testid="named-expected-customers">
            {t('simulation.named_expected_customers', { perReplication: fmtDecimal(perReplication), max: customerBound })}
          </p>
        )}
        {overCustomerBound && expectedPerRun !== null && perReplication !== null && (
          <div role="alert" className="alert alert-error" data-testid="named-customer-bound">
            {t('simulation.named_customer_bound_exceeded', {
              value: fmtDecimal(expectedPerRun), max: customerBound,
              replications: Math.floor(customerBound / perReplication),
            })}
          </div>
        )}
        {!validatedNow && <p className="form-hint">{t('simulation.named_run_needs_validation')}</p>}
        {run.isError && <RequestError error={namedApiError(run.error)} />}
      </section>

      <section className="card" aria-label={t('simulation.named_runs_title')} data-testid="named-runs">
        <h3 className="section-title">{t('simulation.named_runs_title')}</h3>
        {runs.isLoading && <ApiState.Loading />}
        {runs.isError && <ApiState.ErrorState />}
        {runs.data && runs.data.runs.length === 0 && <p className="form-hint">{t('simulation.named_runs_empty')}</p>}
        {runs.data && runs.data.runs.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t('simulation.named_col_run')}</th>
                  <th scope="col">{t('simulation.named_col_created')}</th>
                  <th scope="col">{t('simulation.named_col_dataset')}</th>
                  <th scope="col">{t('simulation.named_replications')}</th>
                  <th scope="col">{t('simulation.named_seed')}</th>
                  <th scope="col">{t('simulation.named_closing_policy_title')}</th>
                  <th scope="col">{t('simulation.named_col_setup')}</th>
                  <th scope="col"><span className="sr-only">{t('simulation.named_open_run')}</span></th>
                </tr>
              </thead>
              <tbody>
                {runs.data.runs.map((item) => (
                  <tr key={item.id} data-testid="named-run-row" aria-selected={selectedRunId === item.id}>
                    <th scope="row">{item.id}</th>
                    <td>{item.created_at}</td>
                    <td>{item.dataset_id}</td>
                    <td>{item.replications}</td>
                    <td>{item.seed}</td>
                    <td>{item.closing_policy}</td>
                    <td>
                      <span className={`badge ${item.setup_matches_current ? 'badge-ok' : 'badge-warn'}`}>
                        {t(item.setup_matches_current ? 'simulation.named_setup_current' : 'simulation.named_setup_earlier')}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="btn-ghost" onClick={() => { setSelectedRunId(item.id); setSelectedReplication(null) }}>
                        {t('simulation.named_open_run')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedRunId !== null && runDetail.isLoading && <ApiState.Loading />}
      {runDetail.isError && <RequestError error={namedApiError(runDetail.error)} />}
      {detail && provenance && (
        <section className="card" data-testid="named-run-evidence" aria-label={t('simulation.named_evidence_title', { id: detail.evidence.id })}>
          <h3 className="section-title">{t('simulation.named_evidence_title', { id: detail.evidence.id })}</h3>
          {!detail.setup_matches_current && (
            <p role="status" className="alert alert-warn">{t('simulation.named_setup_earlier_notice')}</p>
          )}
          <dl>
            <dt>{t('simulation.named_versions')}</dt>
            <dd><code>{provenance.method_version}</code> · <code>{provenance.named_engine_version}</code> · <code>{provenance.state_machine_version}</code> · <code>{provenance.arrival_engine_version}</code></dd>
            <dt>{t('simulation.named_runtime')}</dt>
            <dd>{Object.entries(provenance.runtime).filter(([key]) => key !== 'bit_generator_source').map(([key, value]) => `${key} ${value}`).join(' · ')}</dd>
            <dt>{t('simulation.named_seed')}</dt>
            <dd>{String(provenance.seed)} · {t('simulation.named_root_entropy', { value: provenance.root_entropy })}</dd>
            <dt>{t('simulation.named_dataset_identity')}</dt>
            <dd>{t('simulation.named_dataset_identity_value', {
              id: detail.evidence.params.dataset_id,
              generation: String(detail.evidence.params.dataset_generation).slice(0, 12),
            })}</dd>
            <dt>{t('simulation.named_inputs_sha256')}</dt>
            <dd>
              <code title={provenance.inputs_sha256}>{provenance.inputs_sha256.slice(0, 12)}…</code>{' '}
              <button type="button" className="btn-ghost" onClick={() => { void navigator.clipboard?.writeText(provenance.inputs_sha256) }}>
                {t('simulation.named_copy')}
              </button>
            </dd>
            <dt>{t('simulation.named_agg_verdict')}</dt>
            <dd>{t('simulation.named_no_verdict')} <span className="form-hint">{detail.evidence.result.summary.verdict_reason}</span></dd>
          </dl>
          <button type="button" className="btn-ghost" data-testid="named-load-inputs"
            onClick={() => { setForm(formFromRun(detail.evidence.params.dataset_id, provenance)); setValidated(null) }}>
            {t('simulation.named_load_inputs')}
          </button>
          <NamedReplicationTable rows={detail.evidence.result.replications} summary={detail.evidence.result.summary}
            selectedIndex={selectedReplication} onSelect={setSelectedReplication} />
        </section>
      )}

      {selectedReplication !== null && detail && provenance && (
        <section data-testid="named-selected-replication" aria-label={t('simulation.named_selected_title', { index: selectedReplication })}>
          <h3 className="section-title">{t('simulation.named_selected_title', { index: selectedReplication })}</h3>
          {replication.isFetching && <p role="status" data-testid="named-regenerating">{t('simulation.named_regenerating', { index: selectedReplication })}</p>}
          {replication.isError && <RequestError error={namedApiError(replication.error)} />}
          {replication.data && !replication.isFetching && (
            <>
              <p className="form-hint" data-testid="named-regeneration-status">
                <span className={`badge ${replication.data.regeneration.runtime_matches_recorded ? 'badge-ok' : 'badge-warn'}`}>
                  {t(replication.data.regeneration.runtime_matches_recorded ? 'simulation.named_runtime_matches' : 'simulation.named_runtime_differs')}
                </span>
                {!replication.data.regeneration.runtime_matches_recorded && <> {replication.data.regeneration.basis}</>}
              </p>
              <NamedSharedQueuePlayback playback={replication.data.playback} horizonStartMinute={provenance.inputs.horizon.start_minute} />
              <NamedAttributionTables attribution={replication.data.attribution} />
            </>
          )}
        </section>
      )}
    </div>
  )
}
