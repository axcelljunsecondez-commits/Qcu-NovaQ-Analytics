import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { WorkflowNavigator } from './WorkflowNavigator'

const steps = ['data', 'plans', 'results', 'simulate', 'decision', 'reports'] as const
const labels = ["Data and Setup", 'Suggested Plans', 'Analysis Results', "Queue Simulation", 'Decision', 'Reports'] as const
// Analysis results and Queue simulation live outside the workspace (spec §5); the rest are workspace pages.
const href = (step: string) => (step === 'results' ? '/results?analysis=7'
  : step === 'simulate' ? '/simulation/results?analysis=7' : `/analyses/7/${step}`)

describe('WorkflowNavigator canonical targets', () => {
  it.each(steps.map((step, index) => [step, index] as const).filter(([step]) => step !== 'results' && step !== 'simulate'))(
    'resolves Previous/Next controls for %s',
    (step, index) => {
      renderWithProviders(
        <Routes>
          <Route path="/analyses/:analysisId/:step" element={<WorkflowNavigator />} />
        </Routes>,
        { route: `/analyses/7/${step}` },
      )

      if (index > 0) {
        expect(screen.getByRole('link', { name: `Back: ${labels[index - 1]}` })).toHaveAttribute(
          'href',
          href(steps[index - 1]),
        )
      }
      expect(screen.getByRole('link', { name: labels[index] })).toHaveAttribute('aria-current', 'step')
      labels.forEach((label, position) => expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href(steps[position])))
      if (index < steps.length - 1) {
        expect(screen.getByRole('link', { name: `Next: ${labels[index + 1]}` })).toHaveAttribute(
          'href',
          href(steps[index + 1]),
        )
      } else {
        expect(screen.getByRole('link', { name: 'Finish' })).toHaveAttribute('href', '/analyses')
      }
    },
  )
})

describe('WorkflowNavigator step disclosure (HTML5 redesign Phase B)', () => {
  it('toggles one step list with aria-expanded while all six links stay present', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/:step" element={<WorkflowNavigator />} />
      </Routes>,
      { route: '/analyses/7/plans' },
    )
    const toggle = screen.getByRole('button', { name: /Suggested Plans/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    const list = document.getElementById(toggle.getAttribute('aria-controls') ?? '')
    expect(list?.tagName).toBe('OL')
    expect(document.querySelectorAll('ol')).toHaveLength(1)
    expect(list?.querySelectorAll('a')).toHaveLength(6)
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(list).toHaveClass('is-expanded')
    expect(list?.querySelectorAll('a')).toHaveLength(6)
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    labels.forEach((label) => expect(screen.getByRole('link', { name: label })).toBeInTheDocument())
  })

  it('closes the step list when the page changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/:step" element={<WorkflowNavigator />} />
      </Routes>,
      { route: '/analyses/7/data' },
    )
    await user.click(screen.getByRole('button', { name: /Data and Setup/ }))
    expect(screen.getByRole('button', { name: /Data and Setup/ })).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('link', { name: 'Suggested Plans' }))
    expect(screen.getByRole('button', { name: /Suggested Plans/ })).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('WorkflowNavigator numbered step bar (owner 2026-11-24, "Numbers + current label")', () => {
  afterEach(() => vi.unstubAllGlobals())

  function renderAt(step: string) {
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/:step" element={<WorkflowNavigator />} />
      </Routes>,
      { route: `/analyses/7/${step}` },
    )
  }

  it('names every step link exactly by its label text, without the number', () => {
    renderAt('decision')
    const links = within(document.querySelector('ol')!).getAllByRole('link')
    expect(links).toHaveLength(6)
    links.forEach((link, position) => {
      expect(link).toHaveAccessibleName(labels[position])
      expect(link.querySelector('.workflow-step-number')).toHaveAttribute('aria-hidden', 'true')
      expect(link.querySelector('.workflow-step-label')).toHaveTextContent(labels[position])
    })
  })

  it('keeps a visible label only for the current step in the wide row', () => {
    renderAt('decision')
    expect(document.querySelectorAll('ol > li.active')).toHaveLength(1)
    expect(document.querySelector('ol > li.active a')).toHaveAttribute('aria-current', 'step')
    expect(document.querySelector('ol > li.active .workflow-step-label')).toHaveTextContent('Decision')
    // jsdom does not apply global.css, so pin the wide-row rule that visually hides the other labels.
    const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')
    const wide = css.slice(css.indexOf('@container workflow-footer (min-width: 920px)'))
    expect(wide).toMatch(/\.workflow-stepper li:not\(\.active\) \.workflow-step-label\s*\{[^}]*clip-path: inset\(50%\);/)
    expect(wide.slice(0, wide.indexOf('/* Collapsible long per-period lists.'))).not.toMatch(/overflow-x: auto/)
  })

  it('shows the label as a tooltip on keyboard focus of a numbered step when the row is wide', async () => {
    class WideObserver {
      private readonly callback: ResizeObserverCallback
      constructor(callback: ResizeObserverCallback) { this.callback = callback }
      observe(target: Element) {
        this.callback([{ target, contentBoxSize: [{ inlineSize: 1000, blockSize: 60 }], contentRect: { width: 1000 } } as unknown as ResizeObserverEntry], this as unknown as ResizeObserver)
      }
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal('ResizeObserver', WideObserver)
    renderAt('decision')
    const plans = screen.getByRole('link', { name: 'Suggested Plans' })
    await act(async () => { plans.focus() })
    expect(await screen.findByTestId('tooltip')).toHaveTextContent('Suggested Plans')
    await act(async () => { screen.getByRole('link', { name: 'Decision' }).focus() })
    expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument()
  })
})
