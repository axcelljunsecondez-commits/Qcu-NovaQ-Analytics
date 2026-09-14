import { describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { WorkflowNavigator } from './WorkflowNavigator'

const steps = ['setup', 'current', 'optimize', 'compare', 'simulate', 'decision', 'reports'] as const
const labels = ['Setup', 'Current', 'Optimize', 'Compare', 'Simulate', 'Decision', 'Reports'] as const

describe('WorkflowNavigator canonical targets', () => {
  it.each(steps.map((step, index) => [step, index] as const))(
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
          `/analyses/7/${steps[index - 1]}`,
        )
      }
      expect(screen.getByRole('link', { name: labels[index] })).toHaveAttribute('aria-current', 'step')
      for (const label of labels) expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
      if (index < steps.length - 1) {
        expect(screen.getByRole('link', { name: `Next: ${labels[index + 1]}` })).toHaveAttribute(
          'href',
          `/analyses/7/${steps[index + 1]}`,
        )
      } else {
        expect(screen.getByRole('link', { name: 'Finish' })).toHaveAttribute('href', '/analyses')
      }
    },
  )
})
