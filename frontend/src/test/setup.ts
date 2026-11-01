import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'

// Lazy routes and query notifications can exceed the library's one-second
// default on shared Windows runners. Keep all assertions, with a bounded wait.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})
