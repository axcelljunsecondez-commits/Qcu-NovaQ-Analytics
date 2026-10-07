import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { NamedSharedQueueSimulation } from './NamedSharedQueueSimulation'
import fixture from '../../test/fixtures/sharedNamed.json'

const contractMock = vi.fn()
const validateMock = vi.fn()
const createMock = vi.fn()
const listRunsMock = vi.fn()
const getRunMock = vi.fn()
const replicationMock = vi.fn()
const datasetsMock = vi.fn()

vi.mock('../../api/sharedNamed', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/sharedNamed')>()),
  getNamedContract: (...args: unknown[]) => contractMock(...args),
  validateNamedInputs: (...args: unknown[]) => validateMock(...args),
  createNamedRun: (...args: unknown[]) => createMock(...args),
  listNamedRuns: (...args: unknown[]) => listRunsMock(...args),
  getNamedRun: (...args: unknown[]) => getRunMock(...args),
  getNamedReplication: (...args: unknown[]) => replicationMock(...args),
}))
vi.mock('../../api/analyses', () => ({ listAnalysisDatasets: (...args: unknown[]) => datasetsMock(...args) }))

const ANALYSIS = fixture.analysis_id
const runId = fixture.run.evidence.id

function apiError(status: number, detail: unknown) {
  return Object.assign(new Error(`HTTP ${status}`), { response: { status, data: { detail } } })
}

function render() {
  return renderWithProviders(<NamedSharedQueueSimulation analysisId={ANALYSIS} modeSwitch={<div data-testid="switch" />} />)
}

async function loadRunInputs() {
  render()
  await userEvent.click(await screen.findByRole('button', { name: 'Open run' }))
  await userEvent.click(await screen.findByTestId('named-load-inputs'))
}

beforeEach(() => {
  for (const mock of [contractMock, validateMock, createMock, listRunsMock, getRunMock, replicationMock, datasetsMock]) mock.mockReset()
  contractMock.mockResolvedValue(fixture.contract)
  datasetsMock.mockResolvedValue({
    datasets: [{ id: fixture.dataset_id, analysis_id: ANALYSIS, name: 'Synthetic rates', source_filename: 'synthetic.csv',
      source_format: 'csv', row_count: 2, validation: { ok: true }, created_at: '', normalized: null }],
  })
  listRunsMock.mockResolvedValue(fixture.runs)
  getRunMock.mockResolvedValue(fixture.run_detail)
  validateMock.mockResolvedValue(fixture.validate)
  createMock.mockResolvedValue(fixture.run)
  replicationMock.mockResolvedValue(fixture.replication)
})

describe('NamedSharedQueueSimulation', () => {
  it('shows the persistent banner and the mode switch', async () => {
    render()
    const banner = await screen.findByTestId('named-banner')
    expect(banner).toHaveTextContent('pseudonymous IDs')
    expect(banner).toHaveTextContent(fixture.contract.model_scope)
    expect(banner).toHaveTextContent(fixture.contract.verdict_reason)
    expect(banner).toHaveTextContent('Workforce cost is not shown')
    expect(banner).toHaveTextContent('not production-approved')
    expect(screen.getByTestId('switch')).toBeInTheDocument()
  })

  it('lists the reasons and shows no form when the analysis is ineligible', async () => {
    contractMock.mockResolvedValue({ ...fixture.contract, eligible: false, ineligible_reasons: ['capacity_not_unlimited'] })
    render()
    const box = await screen.findByTestId('named-ineligible')
    expect(box).toHaveTextContent('The Setup capacity is not unlimited.')
    expect(screen.queryByTestId('named-workforce-form')).toBeNull()
  })

  it('enables Run only after a runnable validation of exactly the current form', async () => {
    await loadRunInputs()
    const run = screen.getByRole('button', { name: 'Run' })
    expect(run).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    expect(screen.getByTestId('named-runnable')).toHaveTextContent('Runnable')
    expect(run).toBeDisabled() // replications and seed have no defaults
    await userEvent.type(screen.getByLabelText('Replications'), String(fixture.request.replications))
    await userEvent.type(screen.getByLabelText('Seed'), String(fixture.request.seed))
    expect(run).toBeEnabled()
    const { replications: _r, seed: _s, ...workforce } = fixture.request
    void _r
    void _s
    expect(validateMock).toHaveBeenCalledWith(ANALYSIS, workforce)
    // Any edit makes the validation stale and disables Run again.
    await userEvent.type(screen.getByLabelText('Register count'), '0')
    expect(run).toBeDisabled()
    expect(screen.getByTestId('named-validation-stale')).toBeInTheDocument()
  })

  it('sends the run request built from the validated form and opens the new run', async () => {
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    await userEvent.type(screen.getByLabelText('Replications'), String(fixture.request.replications))
    await userEvent.type(screen.getByLabelText('Seed'), String(fixture.request.seed))
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    await waitFor(() => expect(createMock).toHaveBeenCalledWith(ANALYSIS, fixture.request))
    expect(await screen.findByTestId('named-run-evidence')).toHaveTextContent(`Run ${runId} evidence`)
  })

  it('does not run when validation is not runnable', async () => {
    validateMock.mockResolvedValue({ ...fixture.validate, runnable: false, stage_failed: 'engine', problems: ['The roster is INVALID (X4): too many on duty'] })
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    expect(await screen.findByText('The roster is INVALID (X4): too many on duty')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Replications'), '2')
    await userEvent.type(screen.getByLabelText('Seed'), '5')
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()
  })

  it('shows expected customers and disables Run above the customer bound (spec section 22.8)', async () => {
    expect(fixture.contract.limits.max_expected_customers_per_run).toBe(2900)
    validateMock.mockResolvedValue({ ...fixture.validate, demand: { ...fixture.validate.demand, expected_customers_per_replication: 1450 } })
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    expect(screen.getByTestId('named-expected-customers')).toHaveTextContent('at most 2900 expected customers')
    await userEvent.type(screen.getByLabelText('Seed'), '5')
    await userEvent.type(screen.getByLabelText('Replications'), '3')
    const run = screen.getByRole('button', { name: 'Run' })
    expect(screen.getByTestId('named-customer-bound')).toHaveTextContent('above the limit of 2900. At most 2 replications fit')
    expect(run).toBeDisabled()
    await userEvent.clear(screen.getByLabelText('Replications'))
    await userEvent.type(screen.getByLabelText('Replications'), '2') // 2 x 1450 = 2900 is allowed
    expect(screen.queryByTestId('named-customer-bound')).toBeNull()
    expect(run).toBeEnabled()
  })

  it('shows the server refusal of a run above the customer bound', async () => {
    createMock.mockRejectedValue(apiError(422, {
      code: 'limit_exceeded', limit: 'expected_customers', value: 4350, max: 2900, replications: 3, max_replications: 2,
    }))
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    await userEvent.type(screen.getByLabelText('Replications'), '2')
    await userEvent.type(screen.getByLabelText('Seed'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByTestId('named-error-customer-bound')).toHaveTextContent(
      'This run would have 4350 expected customers, above the limit of 2900. At most 2 replications fit this demand.')
  })

  it('shows a 422 persistence_identity_mismatch as an unsaved run with its checks', async () => {
    createMock.mockRejectedValue(apiError(422, {
      code: 'persistence_identity_mismatch',
      checks: [{ check: 'inputs_fingerprint', message: 'The persisted inputs no longer reproduce the recorded inputs_sha256.' }],
    }))
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    await userEvent.type(screen.getByLabelText('Replications'), '2')
    await userEvent.type(screen.getByLabelText('Seed'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    const box = await screen.findByTestId('named-error-persistence')
    expect(box).toHaveTextContent('The run was not saved')
    expect(box).toHaveTextContent('inputs_fingerprint')
    expect(listRunsMock).toHaveBeenCalledTimes(1) // no refresh: no run was created
  })

  it('regenerates a selected replication with a loading state, then shows playback and attribution', async () => {
    let resolve: (value: unknown) => void = () => {}
    replicationMock.mockReturnValue(new Promise((done) => { resolve = done }))
    render()
    await userEvent.click(await screen.findByRole('button', { name: 'Open run' }))
    const rows = await screen.findAllByTestId('named-replication-row')
    await userEvent.click(within(rows[1]).getByRole('button', { name: 'Open replication' }))
    expect(await screen.findByTestId('named-regenerating')).toHaveTextContent('Regenerating replication 1')
    resolve(fixture.replication)
    expect(await screen.findByTestId('named-playback')).toBeInTheDocument()
    expect(screen.getByTestId('named-attribution')).toBeInTheDocument()
    expect(screen.getByTestId('named-regeneration-status')).toHaveTextContent('Regenerated in the recorded runtime')
    expect(replicationMock).toHaveBeenCalledWith(ANALYSIS, runId, 1)
  })

  it('shows a 409 regeneration_identity refusal and no playback or attribution', async () => {
    replicationMock.mockRejectedValue(apiError(409, {
      code: 'regeneration_identity', check: 'stored_row', message: 'Regenerated replication 0 differs from the stored row.', evidence: {},
    }))
    render()
    await userEvent.click(await screen.findByRole('button', { name: 'Open run' }))
    const rows = await screen.findAllByTestId('named-replication-row')
    await userEvent.click(within(rows[0]).getByRole('button', { name: 'Open replication' }))
    const box = await screen.findByTestId('named-error-regeneration')
    expect(box).toHaveTextContent('regeneration_identity')
    expect(box).toHaveTextContent('stored_row')
    expect(box).toHaveTextContent('differs from the stored row')
    expect(screen.queryByTestId('named-playback')).toBeNull()
    expect(screen.queryByTestId('named-attribution')).toBeNull()
  })

  it('labels a run recorded under an earlier Setup and never presents it as current', async () => {
    listRunsMock.mockResolvedValue({ runs: fixture.runs.runs.map((run) => ({ ...run, setup_matches_current: false })) })
    getRunMock.mockResolvedValue({ ...fixture.run_detail, setup_matches_current: false })
    render()
    expect(await screen.findByText('Earlier Setup')).toBeInTheDocument()
    expect(screen.queryByText('Current Setup')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Open run' }))
    expect(await screen.findByText(/recorded under an earlier Setup/)).toBeInTheDocument()
  })

  it('shows a refused archived run without opening anything', async () => {
    createMock.mockRejectedValue(apiError(409, { code: 'analysis_archived' }))
    await loadRunInputs()
    await userEvent.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByTestId('named-validation')
    await userEvent.type(screen.getByLabelText('Replications'), '2')
    await userEvent.type(screen.getByLabelText('Seed'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByTestId('named-error')).toHaveTextContent('Archived analyses cannot create new named runs.')
  })
})
