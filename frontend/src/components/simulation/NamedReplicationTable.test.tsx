import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { NamedReplicationTable } from './NamedReplicationTable'
import type { NamedReplicationRow, NamedRunSummary } from '../../api/sharedNamed'
import fixture from '../../test/fixtures/sharedNamed.json'
import { fmtDecimal } from '../../lib/format'

const rows = fixture.run.evidence.result.replications as unknown as NamedReplicationRow[]
const summary = fixture.run.evidence.result.summary as unknown as NamedRunSummary

describe('NamedReplicationTable', () => {
  it('shows one row per replication with waits in minutes', () => {
    renderWithProviders(<NamedReplicationTable rows={rows} summary={summary} selectedIndex={null} onSelect={() => {}} />)
    const rendered = screen.getAllByTestId('named-replication-row')
    expect(rendered).toHaveLength(rows.length)
    rows.forEach((row, index) => {
      const cells = within(rendered[index])
      expect(cells.getByText(fmtDecimal((row.waiting.mean_wait_hours as number) * 60))).toBeInTheDocument()
      expect(cells.getByText(fmtDecimal(row.closing.run_after_closing_hours * 60))).toBeInTheDocument()
    })
  })

  it('renders null as a dash, never 0', () => {
    const withNull = [{ ...rows[0], waiting: { ...rows[0].waiting, mean_wait_hours: null } }]
    renderWithProviders(<NamedReplicationTable rows={withNull} summary={summary} selectedIndex={null} onSelect={() => {}} />)
    const cells = within(screen.getByTestId('named-replication-row')).getAllByRole('cell')
    expect(cells[4]).toHaveTextContent('—')
  })

  it('shows the Student-t interval with n and n_undefined', () => {
    renderWithProviders(<NamedReplicationTable rows={rows} summary={summary} selectedIndex={null} onSelect={() => {}} />)
    const means = summary.waiting_time.mean_of_replication_means_hours
    const text = screen.getByTestId('named-agg-mean-of-means').textContent ?? ''
    expect(text).toContain(fmtDecimal((means.mean as number) * 60))
    expect(text).toContain(fmtDecimal((means.ci_lower as number) * 60))
    expect(text).toContain(fmtDecimal((means.ci_upper as number) * 60))
    expect(text).toContain(`n = ${means.n}`)
    expect(text).toContain(`undefined = ${means.n_undefined}`)
    expect(screen.getByText('Descriptive frequencies, not failure rates.')).toBeInTheDocument()
  })

  it('renders no PASS, FAIL, verdict value, cost, or ROI', () => {
    renderWithProviders(<NamedReplicationTable rows={rows} summary={summary} selectedIndex={null} onSelect={() => {}} />)
    // The only mentions allowed are the disclaimers that no such rule exists: the backend's
    // verdict_reason and this view's own "no PASS or FAIL" note.
    const text = (screen.getByTestId('named-replication-table').textContent ?? '')
      .replace(summary.verdict_reason, '')
      .replace('There is no PASS or FAIL and no verdict.', '')
    expect(text).not.toMatch(/\bPASS\b|\bFAIL(ED)?\b|\bROI\b|cost/i)
    expect(screen.getByText('None.')).toBeInTheDocument()
  })

  it('selects a replication', async () => {
    const onSelect = vi.fn()
    renderWithProviders(<NamedReplicationTable rows={rows} summary={summary} selectedIndex={null} onSelect={onSelect} />)
    await userEvent.click(within(screen.getAllByTestId('named-replication-row')[2]).getByRole('button'))
    expect(onSelect).toHaveBeenCalledWith(2)
  })
})
