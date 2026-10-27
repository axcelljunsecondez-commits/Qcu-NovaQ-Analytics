import { describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { WorkflowNavigator } from './WorkflowNavigator'

const steps = ['data', 'plans', 'results', 'simulate', 'decision', 'reports'] as const
const labels = ["Data and Setup", 'Suggested plans', 'Analysis results', "Queue Simulation", 'Decision', 'Reports'] as const
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
