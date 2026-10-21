import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { StrictMode } from 'react'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { renderWithProviders } from '../../test/test-utils'
import { TUTORIALS, tutorialDuration, tutorialFile } from '../../lib/tutorials'
import { TutorialWatch } from './TutorialWatch'
import { VideoTutorials } from './VideoTutorials'

vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))
const pause = vi.fn()
const descriptors = new Map<string, PropertyDescriptor | undefined>()
beforeAll(() => {
  for (const key of ['showModal', 'close']) descriptors.set(key, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, key))
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', '') } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open') } })
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause)
})
beforeEach(() => pause.mockClear())
afterAll(() => {
  for (const [key, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, key, descriptor)
    else Reflect.deleteProperty(HTMLDialogElement.prototype, key)
  }
  vi.restoreAllMocks()
})

describe('Tutorials: app behavior (media and native dialog are stubbed in JSDOM)', () => {
  it('does not mount a video or its source before Watch is selected', () => {
    const { container } = renderWithProviders(<VideoTutorials query="" />)
    expect(container.querySelector('video')).toBeNull()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Watch / })).toHaveLength(3)
  })

  it.each(TUTORIALS)('opens the matching $id media, captions and steps', async (tutorial) => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id={tutorial.id} />)
    const trigger = screen.getByRole('button', { name: 'Watch tutorial' })
    await user.click(trigger)
    const title = en[`tutorials.${tutorial.id}.title`]
    const dialog = screen.getByRole('dialog', { name: title })
    const video = within(dialog).getByLabelText(title)
    expect(video).toHaveAttribute('src', tutorialFile(tutorial, 'mp4'))
    expect(video).toHaveAttribute('controls')
    expect(video).toHaveAttribute('playsinline')
    expect(video).not.toHaveAttribute('autoplay')
    expect(within(dialog).getByText(new RegExp(tutorialDuration(tutorial)))).toHaveTextContent('English captions and steps')
    expect(within(dialog).getByRole('link', { name: 'Download video' })).toHaveAttribute('href', tutorialFile(tutorial, 'mp4'))
    expect(within(dialog).getByRole('link', { name: 'Download captions' })).toHaveAttribute('href', tutorialFile(tutorial, 'vtt'))
    expect(within(dialog).getByRole('button', { name: 'Close' })).toHaveFocus()
    expect(within(dialog).getByText('Read the steps')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.querySelector('video')).toBeNull()
    expect(trigger).toHaveFocus()
    expect(pause).toHaveBeenCalled()
  })

  it('cleans up on native Escape cancellation and can reopen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="key-metrics" />)
    const trigger = screen.getByRole('button', { name: 'Watch tutorial' })
    await user.click(trigger)
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { bubbles: true, cancelable: true }))
    expect(document.querySelector('video')).toBeNull()
    expect(trigger).toHaveFocus()
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: 'Analysis key metrics' })).toBeInTheDocument()
  })

  it('pauses the video when its page unmounts', async () => {
    const user = userEvent.setup()
    const view = renderWithProviders(<TutorialWatch id="queue-simulation" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    pause.mockClear()
    view.unmount()
    expect(pause).toHaveBeenCalledOnce()
  })

  it('keeps the selected video source and close focus in StrictMode', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StrictMode><TutorialWatch id="analysis-workflow" /></StrictMode>)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    expect(document.querySelector('video')).toHaveAttribute('src', tutorialFile(TUTORIALS[0], 'mp4'))
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
  })

  it('shows a download fallback when the media element reports an error', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="analysis-workflow" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    fireEvent.error(document.querySelector('video')!)
    expect(screen.getByRole('alert')).toHaveTextContent('Use Download video')
    expect(screen.getByRole('link', { name: 'Download video' })).toBeInTheDocument()
  })

  it('filters the library with every search word and hides it for no match', () => {
    const view = renderWithProviders(<VideoTutorials query="key metrics" />)
    expect(screen.getByRole('heading', { name: 'Analysis key metrics' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'My analyses to reports' })).not.toBeInTheDocument()
    view.rerender(<VideoTutorials query="no-such-video" />)
    expect(screen.queryByRole('region', { name: 'Video tutorials' })).not.toBeInTheDocument()
  })

  it('uses Tagalog controls and explicitly names the English captions/steps', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="key-metrics" />, { lang: 'tl' })
    await user.click(screen.getByRole('button', { name: 'Manood ng gabay' }))
    expect(screen.getByRole('dialog', { name: tl['tutorials.key-metrics.title'] })).toBeInTheDocument()
    expect(screen.getByText(/Ingles ang mga caption at hakbang/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Isara' })).toHaveFocus()
  })

  it('keeps tutorial UI keys symmetric in both languages', () => {
    const keys = (object: Record<string, unknown>) => Object.keys(object).filter((key) => key.startsWith('tutorials.')).sort()
    expect(keys(en)).toEqual(keys(tl))
    for (const key of keys(en)) {
      expect((en as Record<string, string>)[key]?.trim()).toBeTruthy()
      expect((tl as Record<string, string>)[key]?.trim()).toBeTruthy()
    }
  })

  it('ships exact verified MP4s below 25 MiB with matching captions and posters', () => {
    const root = join(__dirname, '../../../public/tutorials')
    for (const tutorial of TUTORIALS) {
      const bytes = readFileSync(join(root, `${tutorial.id}.mp4`))
      expect(bytes.length).toBe(tutorial.bytes)
      expect(bytes.length).toBeLessThan(25 * 1024 ** 2)
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(tutorial.sha256)
      expect(tutorial.revision).toBe(tutorial.sha256.slice(0, 12))
      expect(readFileSync(join(root, `${tutorial.id}.vtt`), 'utf8')).toMatch(/^WEBVTT/)
      const poster = readFileSync(join(root, `${tutorial.id}.webp`))
      expect(poster.toString('ascii', 0, 4)).toBe('RIFF')
      expect(poster.toString('ascii', 8, 12)).toBe('WEBP')
    }
  })
})
