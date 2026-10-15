import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { ReportsPage } from './ReportsPage'

const listAnalysesMock = vi.fn()
const getAnalysisMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const previewMock = vi.fn()
const fileMock = vi.fn()
const fetchReportMock = vi.fn()
const createObjectURLMock = vi.fn()
const revokeObjectURLMock = vi.fn()
let clickSpy: ReturnType<typeof vi.spyOn>

vi.mock('../api/analyses', () => ({
  listAnalyses: (...args: unknown[]) => listAnalysesMock(...args),
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
}))

vi.mock('../api/reports', async () => {
  const actual = await vi.importActual<typeof import('../api/reports')>('../api/reports')
  return {
    ...actual,
    fetchReportPreview: (...args: unknown[]) => previewMock(...args),
    fetchReportFile: (...args: unknown[]) => fileMock(...args),
    fetchReport: (...args: unknown[]) => fetchReportMock(...args),
  }
})

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const analysis = { id: 7, name: 'Main branch', archived_at: null, queue_setup: { queue_structure: 'shared_queue' } }
const datasets = [
  { id: 3, name: 'March records', validation: { ok: true } },
  { id: 4, name: 'Broken upload', validation: { ok: false } },
]
const PLAN_CONTENTS = { pdf: ['Key results: now and with the plan', 'By period'],
  excel: ['Overview', 'Your data', 'Plan', 'Formula check', 'Plan search', 'Assumptions', 'Provenance'] }
const AFTER = { pdf: ['Decision', 'Simulation key results', 'Checks', 'What is not included'], excel: ['Simulation', 'Checks', 'Decision'] }
const planPreview = { model: { report: 'plan', line_type: 'shared', cover: { label: '', plan_name: 'Four at eight', analysis_name: 'Main branch' } },
  contents: PLAN_CONTENTS, after_checks: AFTER }
const fullPreview = {
  model: { report: 'full', line_type: 'shared', cover: { label: '', plan_name: 'Four at eight', analysis_name: 'Main branch' },
    decision: { status: 'adopt', headline: 'Adopt Scenario "Four at eight".', recommendation: '' } },
  contents: { pdf: [...PLAN_CONTENTS.pdf, ...AFTER.pdf], excel: ['Overview', 'Your data', 'Plan', 'Formula check', 'Plan search',
    'Simulation', 'Checks', 'Decision', 'Assumptions', 'Provenance'] },
  after_checks: { pdf: [], excel: [] },
}
const refused = (status: number, detail: unknown) => Object.assign(new Error('refused'), { response: { status, data: { detail } } })

function Address() {
  const location = useLocation()
  return <output data-testid="address">{location.pathname}{location.search}</output>
}

function renderReports(route = '/reports?analysis=7', lang: 'en' | 'tl' = 'en') {
  return renderWithProviders(
    <Routes>
      <Route path="/reports" element={<><ReportsPage /><Address /></>} />
      <Route path="/analyses" element={<Address />} />
    </Routes>,
    { route, lang },
  )
}

beforeEach(() => {
  for (const mock of [listAnalysesMock, getAnalysisMock, listAnalysisDatasetsMock, previewMock, fileMock, fetchReportMock]) mock.mockReset()
  listAnalysesMock.mockResolvedValue({ analyses: [analysis] })
  getAnalysisMock.mockResolvedValue({ analysis })
  listAnalysisDatasetsMock.mockResolvedValue({ datasets })
  fileMock.mockResolvedValue(new Blob(['%PDF']))
  fetchReportMock.mockResolvedValue(new Blob(['data']))
  createObjectURLMock.mockReturnValue('blob:report')
  vi.stubGlobal('URL', { ...URL, createObjectURL: createObjectURLMock, revokeObjectURL: revokeObjectURLMock })
  clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})

afterEach(() => {
  clickSpy.mockRestore()
  vi.unstubAllGlobals()
})

describe('Reports page (B8, D33)', () => {
  it('offers only the data report until a plan is chosen', async () => {
    previewMock.mockRejectedValue(refused(422, { code: 'no_selected_plan', detail: 'Choose a plan in Suggested plans first.' }))
    renderReports()
    expect(await screen.findByText('No plan chosen yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Suggested plans' })).toHaveAttribute('href', '/analyses/7/plans')
    expect(screen.queryByTestId('report-card-pdf')).not.toBeInTheDocument()
    expect(previewMock).toHaveBeenCalledTimes(1)  // no full report is asked for without a plan
    const data = screen.getByTestId('report-card-data')
    expect(within(data).getAllByRole('option').map((option) => option.textContent)).toEqual(['March records'])  // processed files only
    await userEvent.setup().click(within(data).getByRole('button', { name: 'Download data (Excel)' }))
    await waitFor(() => expect(fetchReportMock).toHaveBeenCalledWith('datasets', 3, 'excel', 7))
  })

  it('says a plan is out of date with the server reason', async () => {
    previewMock.mockRejectedValue(refused(422, { code: 'plan_not_current', detail: 'Scenario setup changed.' }))
    renderReports()
    expect(await screen.findByText('Out of date:')).toBeInTheDocument()
    expect(screen.getByText('Scenario setup changed.')).toBeInTheDocument()
    expect(screen.queryByTestId('report-card-excel')).not.toBeInTheDocument()
  })

  it('stamps a calculated plan, lists the file contents and what comes after the checks, and downloads the plan files', async () => {
    previewMock.mockImplementation(async (_id: number, level: string) => {
      if (level === 'plan') return planPreview
      throw refused(404, 'Run selected-plan Monte Carlo before generating the final report.')
    })
    const user = userEvent.setup()
    renderReports()
    expect(await screen.findByText('Calculated only · not checked by simulation')).toBeInTheDocument()
    expect(screen.getByTestId('full-reason')).toHaveTextContent('Run selected-plan Monte Carlo before generating the final report.')
    const pdf = screen.getByTestId('report-card-pdf')
    expect(within(pdf).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Key results: now and with the plan', 'By period', 'Decision (after the checks)', 'Simulation key results (after the checks)',
      'Checks (after the checks)', 'What is not included (after the checks)'])
    await user.click(within(pdf).getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => expect(fileMock).toHaveBeenCalledWith(7, 'plan', 'pdf'))
    await user.click(within(screen.getByTestId('report-card-excel')).getByRole('button', { name: 'Download Excel' }))
    await waitFor(() => expect(fileMock).toHaveBeenCalledWith(7, 'plan', 'xlsx'))
    expect(await screen.findByText('Report downloaded.')).toBeInTheDocument()
  })

  it('stamps the full report with the Decision and downloads the full files', async () => {
    previewMock.mockImplementation(async (_id: number, level: string) => (level === 'plan' ? planPreview : fullPreview))
    renderReports()
    expect(await screen.findByText('Checked by simulation · Decision: Adopt')).toBeInTheDocument()
    expect(screen.getByTestId('report-decision-plain')).toHaveTextContent('Yes, go ahead with this plan. It passed every check and costs the same or less.')
    expect(screen.getByText('Plan: Four at eight')).toBeInTheDocument()
    expect(screen.getByTestId('full-stamp')).toHaveClass('badge-ok')
    const excel = screen.getByTestId('report-card-excel')
    expect(within(excel).getAllByRole('listitem').map((item) => item.textContent)).toContain('Decision')
    expect(within(excel).queryByText(/after the checks/)).not.toBeInTheDocument()
    await userEvent.setup().click(within(excel).getByRole('button', { name: 'Download Excel' }))
    await waitFor(() => expect(fileMock).toHaveBeenCalledWith(7, 'full', 'xlsx'))
  })

  it('colours the full stamp by the Decision: a Revise is not shown in green (U10 F9)', async () => {
    const revise = { ...fullPreview, model: { ...fullPreview.model, decision: { status: 'revise', headline: 'Do not adopt yet.', recommendation: '' } } }
    previewMock.mockImplementation(async (_id: number, level: string) => (level === 'plan' ? planPreview : revise))
    renderReports()
    expect(await screen.findByText('Checked by simulation · Decision: Revise')).toBeInTheDocument()
    expect(screen.getByTestId('full-stamp')).toHaveClass('badge-bad')
    expect(screen.getByTestId('full-stamp')).not.toHaveClass('badge-ok')
  })

  it("states the Decision in the reader's language from its stored fields, not the server headline", async () => {
    const withDecision = (decision: Record<string, unknown>, lineType = 'shared') => ({ ...fullPreview,
      model: { ...fullPreview.model, line_type: lineType, decision: { headline: 'Do not adopt Scenario "Four at eight" yet.', recommendation: '', ...decision } } })
    const show = async (preview: unknown, lang: 'en' | 'tl' = 'en') => {
      previewMock.mockImplementation(async (_id: number, level: string) => (level === 'plan' ? planPreview : preview))
      const view = renderReports('/reports?analysis=7', lang)
      const text = (await screen.findByTestId('report-decision-plain')).textContent
      view.unmount()
      return text
    }
    const failed = withDecision({ status: 'revise', missing_evidence: [], facts: { failed_periods: ['segment_1'], failed_intervals: 1, validation_intervals: 4 } })
    expect(await show(failed)).toBe('Change the plan first. It did not hold up in: segment_1')
    expect(await show(failed, 'tl')).toBe('Baguhin muna ang plano. Hindi ito tumagal sa: segment_1')
    // An older shared Decision has only the interval counts.
    expect(await show(withDecision({ status: 'revise', facts: { failed_intervals: 2, validation_intervals: 12 } })))
      .toBe('Change the plan first. It did not hold up in 2 of 12 periods.')
    expect(await show(withDecision({ status: 'insufficient_evidence', missing_evidence: ['completed Setup'], facts: {} })))
      .toBe('Not enough checks yet. Run: completed Setup')
    // Separate-lane counts are line-periods, so they are never shown as periods.
    expect(await show(withDecision({ status: 'revise', facts: { failed_intervals: 2, validation_intervals: 12 } }, 'separate')))
      .toBe('Change the plan first.')
    expect(await show(withDecision({ status: 'conditional', facts: { today_overloaded_periods: ['09:00'] } }, 'separate')))
      .toBe("The plan passed every check, but its cost saving can't be calculated for separate lines. Use it only if you accept the cost.")
    expect(await show(withDecision({ status: 'something_new', facts: null }))).toBe('Do not adopt Scenario "Four at eight" yet.')
  })

  it('shows a refused download as an alert', async () => {
    previewMock.mockImplementation(async (_id: number, level: string) => (level === 'plan' ? planPreview : fullPreview))
    fileMock.mockRejectedValue(refused(422, { code: 'no_current_decision', detail: 'Make the Decision on the Checks and decision page first.' }))
    renderReports()
    await userEvent.setup().click(within(await screen.findByTestId('report-card-pdf')).getByRole('button', { name: 'Download PDF' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Make the Decision on the Checks and decision page first.')
  })

  it('shows any other refusal as an error, not as an out-of-date plan', async () => {
    previewMock.mockRejectedValue(refused(500, 'Internal error'))
    renderReports()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('Out of date:')).not.toBeInTheDocument()
    expect(screen.queryByTestId('report-stamp')).not.toBeInTheDocument()
  })

  it('remembers the analysis it shows', async () => {
    window.localStorage.removeItem('novaq_last_analysis')
    previewMock.mockResolvedValue(planPreview)
    renderReports()
    await waitFor(() => expect(window.localStorage.getItem('novaq_last_analysis')).toBe('7'))
  })

  it('opens the last analysis when none is in the address', async () => {
    window.localStorage.setItem('novaq_last_analysis', '7')
    previewMock.mockResolvedValue(planPreview)
    renderReports('/reports')
    await waitFor(() => expect(screen.getAllByTestId('address')[0]).toHaveTextContent('/reports?analysis=7'))
  })
})
