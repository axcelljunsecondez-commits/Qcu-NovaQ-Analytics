import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup, configure } from '@testing-library/react'
import React from 'react'

// Lazy routes and query notifications can exceed the library's one-second
// default on shared Windows runners. Keep all assertions, with a bounded wait.
configure({ asyncUtilTimeout: 5000 })

vi.mock('react-plotly.js', () => ({
  default: () => React.createElement('div', { className: 'plotly' }),
}))

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})
