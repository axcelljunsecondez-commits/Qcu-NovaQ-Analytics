import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// Owner decision 2026-11-24: one fixed Dark Navy and Brass theme, no switcher and no light tokens.
describe('theme tokens', () => {
  const css = readFileSync(resolve(process.cwd(), 'src/styles/theme.css'), 'utf8')

  it('declares the dark color scheme only', () => {
    expect(css).toMatch(/:root\s*\{[^}]*color-scheme: dark;/)
    expect(css).not.toMatch(/color-scheme:\s*light/)
  })
})
