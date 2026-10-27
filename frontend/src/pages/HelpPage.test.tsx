import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Outlet, Route, Routes } from 'react-router-dom'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'
import { PublicShell } from '../components/layout/PublicShell'
import { HELP_FIGURES, HELP_GUIDES, helpFigureSrc, type HelpTopic } from '../lib/helpGuides'
import { renderWithProviders } from '../test/test-utils'
import { HelpPage } from './HelpPage'

const meMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(async () => ({ user: null })),
  logout: vi.fn(async () => ({})),
}))

vi.mock('../components/layout/AppLayout', () => ({
  AppLayout: () => <div data-testid="app-layout"><Outlet /></div>,
}))

beforeEach(() => {
  meMock.mockReset()
  meMock.mockRejectedValue(Object.assign(new Error('Not signed in'), { status: 401 }))
  Element.prototype.scrollIntoView = vi.fn()
})

function renderHelp(route: string, lang: 'en' | 'tl' = 'en') {
  return renderWithProviders(
    <Routes>
      <Route element={<PublicShell />}>
        <Route path="/help" element={<HelpPage />} />
        <Route path="/help/:topic" element={<HelpPage />} />
      </Route>
      <Route path="/" element={<div>home-marker</div>} />
    </Routes>,
    { route, lang },
  )
}

const PUBLIC_DIR = join(__dirname, '..', '..', 'public')

/** Width and height from a WebP file header (simple VP8, lossless VP8L or extended VP8X). */
function webpSize(path: string): [number, number] {
  const bytes = readFileSync(path)
  expect(bytes.toString('ascii', 0, 4)).toBe('RIFF')
  expect(bytes.toString('ascii', 8, 12)).toBe('WEBP')
  const chunk = bytes.toString('ascii', 12, 16)
  if (chunk === 'VP8X') return [bytes.readUIntLE(24, 3) + 1, bytes.readUIntLE(27, 3) + 1]
  if (chunk === 'VP8 ') return [bytes.readUInt16LE(26) & 0x3fff, bytes.readUInt16LE(28) & 0x3fff]
  if (chunk === 'VP8L') {
    const bits = bytes.readUInt32LE(21)
    return [(bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1]
  }
  throw new Error(`Unknown WebP chunk ${chunk} in ${path}`)
}

describe('Help center (plan U8)', () => {
  it('lists every guide and is readable without signing in', async () => {
    renderHelp('/help')
    const guides = await screen.findByRole('region', { name: 'Guides' })
    expect(within(guides).getAllByRole('link').map((link) => link.textContent)).toEqual([
      "Starting an Analysis", "Adding Your Data", "Reading Results", "Comparing Plans", "Queue Simulation",
      'Checks and Decision', 'Downloads', 'Problems'])
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(screen.queryByTestId('app-layout')).not.toBeInTheDocument()
  })

  it('shows Help inside the app when signed in', async () => {
    meMock.mockResolvedValue({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })
    renderHelp('/help')
    expect(await screen.findByTestId('app-layout')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Help' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('finds sections by every word of the search and links to them', async () => {
    const user = userEvent.setup()
    renderHelp('/help')
    await user.type(await screen.findByLabelText("Find Help"), 'closing time')
    const results = screen.getByRole('list', { name: 'Search results' })
    expect(within(results).getByRole('link', { name: 'Queue Simulation: Closing time' })).toHaveAttribute('href', '/help/simulation#closing')
    await user.clear(screen.getByLabelText("Find Help"))
    await user.type(screen.getByLabelText("Find Help"), 'review only')
    expect(within(screen.getByRole('list', { name: 'Search results' })).getByRole('link', {
      name: 'Adding Your Data: Planning file or review-only file' })).toHaveAttribute('href', '/help/data#purpose')
    await user.clear(screen.getByLabelText("Find Help"))
    await user.type(screen.getByLabelText("Find Help"), 'closing zebra')
    expect(screen.getByRole('status')).toHaveTextContent('No guide mentions all of these words.')
    await user.clear(screen.getByLabelText("Find Help"))
    await user.type(screen.getByLabelText("Find Help"), 'exponential')  // in a section's text, not its title
    expect(within(screen.getByRole('list', { name: 'Search results' })).getAllByRole('link').map((link) => link.textContent))
      .toEqual(['Queue Simulation: Service times'])
  })

  it('opens a guide with what to do, why, the next step and its sections, at the linked section', async () => {
    renderHelp('/help/simulation#closing')
    expect(await screen.findByRole('heading', { level: 1, name: "Queue Simulation" })).toBeInTheDocument()
    expect(screen.getByText('What to do')).toBeInTheDocument()
    expect(screen.getByText('Open Queue simulation, choose Current or Suggested plan, and run it.')).toBeInTheDocument()
    expect(screen.getByText('Next step')).toBeInTheDocument()
    const closing = screen.getByRole('region', { name: 'Closing time' })
    expect(closing).toHaveAttribute('id', 'closing')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'All guides' })).toHaveAttribute('href', '/help')
  })

  it('sends an unknown guide back to the list', async () => {
    renderHelp('/help/nonsense')
    expect(await screen.findByRole('region', { name: 'Guides' })).toBeInTheDocument()
  })

  it("shows the guide picture in the reader's language with its numbered list", async () => {
    renderHelp('/help/checks')
    const picture = await screen.findByRole('img', { name: en['help.guide.checks.figure_alt'] })
    expect(picture).toHaveAttribute('src', '/help-images/en/checks.webp')
    expect(picture).toHaveAttribute('width', '1080')
    expect(picture).toHaveAttribute('height', '357')
    const figure = picture.closest('figure')!
    expect(within(figure).getByText('Sample screen with made-up data. The numbers match the list below.')).toBeInTheDocument()
    expect(within(figure).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'The Decision, the periods that did not hold up, and the run it uses.',
      "Each period: the busy share in the full-day run against the plan's target, and how many variations failed.",
      'Check the plan: runs the required checks, then makes the Decision.',
    ])
  })

  it('uses the Tagalog picture and list in Tagalog', async () => {
    renderHelp('/help/simulation', 'tl')
    const picture = await screen.findByRole('img', { name: tl['help.guide.simulation.figure_alt'] })
    expect(picture).toHaveAttribute('src', '/help-images/tl/simulation.webp')
    expect(picture).toHaveAttribute('height', '684')
    expect(screen.getByRole('heading', { level: 1, name: 'Queue Simulation' })).toHaveAttribute('lang', 'en')
    const items = within(picture.closest('figure')!).getAllByRole('listitem')
    expect(items).toHaveLength(4)
    expect(items[3]).toHaveTextContent(tl['help.guide.simulation.figure_mark_4'])
  })

  it('shows no picture for Problems, which covers several screens', async () => {
    renderHelp('/help/problems')
    expect(await screen.findByRole('heading', { level: 1, name: 'Problems' })).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('has each picture file at its stated size and a caption for every number, in both languages', () => {
    const english = en as Record<string, string>
    const tagalog = tl as Record<string, string>
    const figures = Object.entries(HELP_FIGURES) as [HelpTopic, NonNullable<(typeof HELP_FIGURES)[HelpTopic]>][]
    expect(figures.map(([topic]) => topic)).toEqual(['start', 'data', 'results', 'plans', 'simulation', 'checks', 'downloads'])
    for (const language of ['en', 'tl'] as const) {
      const strings = language === 'en' ? english : tagalog
      expect(readdirSync(join(PUBLIC_DIR, 'help-images', language)).sort())
        .toEqual(figures.map(([topic]) => `${topic}.webp`).sort())
      for (const [topic, figure] of figures) {
        expect(webpSize(join(PUBLIC_DIR, helpFigureSrc(topic, language)))).toEqual([...figure.size[language]])
        const base = `help.guide.${topic}`
        expect(strings[`${base}.figure_alt`]?.trim()).toBeTruthy()
        for (let mark = 1; mark <= figure.marks; mark += 1) expect(strings[`${base}.figure_mark_${mark}`]?.trim()).toBeTruthy()
        expect(strings[`${base}.figure_mark_${figure.marks + 1}`]).toBeUndefined()
      }
    }
    expect(english['help.guide.problems.figure_alt']).toBeUndefined()
  })

  it('has every guide text in English and Tagalog', () => {
    const keys = HELP_GUIDES.flatMap(({ topic, sections }) => [
      ...['title', 'action', 'purpose', 'next'].map((part) => `help.guide.${topic}.${part}`),
      ...sections.flatMap((section) => [`help.guide.${topic}.${section}.title`, `help.guide.${topic}.${section}.body`]),
    ])
    const english = en as Record<string, string>
    const tagalog = tl as Record<string, string>
    expect(keys.filter((key) => !english[key]?.trim())).toEqual([])
    expect(keys.filter((key) => !tagalog[key]?.trim())).toEqual([])
  })
})
