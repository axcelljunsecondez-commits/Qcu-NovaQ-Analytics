import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import React from 'react'

vi.mock('react-plotly.js', () => ({
  default: () => React.createElement('div', { className: 'plotly' }),
}))

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})
