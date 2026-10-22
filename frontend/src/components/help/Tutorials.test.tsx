import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { StrictMode } from 'react'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { renderWithProviders } from '../../test/test-utils'
import { TUTORIALS, tutorialDuration, tutorialFile } from '../../lib/tutorials'
import { TutorialWatch } from './TutorialWatch'
import { VideoTutorials } from './VideoTutorials'

vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))
const pause = vi.fn()
const fetchClip = vi.fn<typeof fetch>()
const createObjectURL = vi.fn<(blob: Blob) => string>()
const revokeObjectURL = vi.fn<(url: string) => void>()
const descriptors = new Map<string, PropertyDescriptor | undefined>()
const urlDescriptors = new Map<string, PropertyDescriptor | undefined>()
let nextUrl = 0

function clipResponse(bytes = TUTORIALS[0].bytes as number, type = 'video/mp4') {
  return new Response(new Uint8Array(bytes), { headers: { 'Content-Type': type } })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

async function loadedVideo() {
  const video = document.querySelector('video')!
  await waitFor(() => expect(video).toHaveAttribute('src', expect.stringMatching(/^blob:/)))
  return video
}

beforeAll(() => {
  for (const key of ['showModal', 'close']) descriptors.set(key, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, key))
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', '') } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open') } })
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause)
  for (const key of ['createObjectURL', 'revokeObjectURL']) urlDescriptors.set(key, Object.getOwnPropertyDescriptor(URL, key))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
})
beforeEach(() => {
  pause.mockClear()
  fetchClip.mockReset()
  createObjectURL.mockReset()
  revokeObjectURL.mockReset()
  nextUrl = 0
  createObjectURL.mockImplementation(() => `blob:https://novaq.test/tutorial-${++nextUrl}`)
  fetchClip.mockImplementation(async (input) => {
    const tutorial = TUTORIALS.find((item) => tutorialFile(item, 'mp4') === String(input))
    if (!tutorial) throw new Error('Unexpected test request')
    return clipResponse(tutorial.bytes)
  })
  vi.stubGlobal('fetch', fetchClip)
})
afterEach(() => vi.unstubAllGlobals())
afterAll(() => {
  for (const [key, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, key, descriptor)
    else Reflect.deleteProperty(HTMLDialogElement.prototype, key)
  }
  for (const [key, descriptor] of urlDescriptors) {
    if (descriptor) Object.defineProperty(URL, key, descriptor)
    else Reflect.deleteProperty(URL, key)
  }
  vi.restoreAllMocks()
})

describe('Tutorials: app behavior (media and native dialog are stubbed in JSDOM)', () => {
  it('does not mount a video or its source before Watch is selected', () => {
    const { container } = renderWithProviders(<VideoTutorials query="" />)
    expect(container.querySelector('video')).toBeNull()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Watch / })).toHaveLength(3)
    expect(fetchClip).not.toHaveBeenCalled()
    expect(createObjectURL).not.toHaveBeenCalled()
  })

  it.each(TUTORIALS)('opens the matching $id media, captions and steps', async (tutorial) => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id={tutorial.id} />)
    const trigger = screen.getByRole('button', { name: 'Watch tutorial' })
    await user.click(trigger)
    const title = en[`tutorials.${tutorial.id}.title`]
    const dialog = screen.getByRole('dialog', { name: title })
    const video = within(dialog).getByLabelText(title)
    await loadedVideo()
    expect(fetchClip).toHaveBeenCalledOnce()
    expect(fetchClip).toHaveBeenCalledWith(tutorialFile(tutorial, 'mp4'), { signal: expect.any(AbortSignal) })
    expect(createObjectURL).toHaveBeenCalledWith(expect.objectContaining({ size: tutorial.bytes, type: 'video/mp4' }))
    const source = video.getAttribute('src')!
    const signal = fetchClip.mock.calls[0][1]!.signal!
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
    expect(signal.aborted).toBe(true)
    expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith(source)
  })

  it('cleans up on native Escape cancellation and can reopen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="key-metrics" />)
    const trigger = screen.getByRole('button', { name: 'Watch tutorial' })
    await user.click(trigger)
    const firstSource = (await loadedVideo()).getAttribute('src')!
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { bubbles: true, cancelable: true }))
    expect(document.querySelector('video')).toBeNull()
    expect(trigger).toHaveFocus()
    expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith(firstSource)
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: 'Analysis key metrics' })).toBeInTheDocument()
    expect((await loadedVideo()).getAttribute('src')).not.toBe(firstSource)
  })

  it('pauses the video when its page unmounts', async () => {
    const user = userEvent.setup()
    const view = renderWithProviders(<TutorialWatch id="queue-simulation" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    const source = (await loadedVideo()).getAttribute('src')!
    pause.mockClear()
    view.unmount()
    expect(pause).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith(source)
    expect(fetchClip.mock.calls[0][1]!.signal!.aborted).toBe(true)
  })

  it('keeps the selected video source and close focus in StrictMode', async () => {
    const user = userEvent.setup()
    renderWithProviders(<StrictMode><TutorialWatch id="analysis-workflow" /></StrictMode>)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    const source = (await loadedVideo()).getAttribute('src')!
    expect(fetchClip).toHaveBeenCalledTimes(2)
    expect(fetchClip.mock.calls[0][1]!.signal!.aborted).toBe(true)
    expect(fetchClip.mock.calls[1][1]!.signal!.aborted).toBe(false)
    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(revokeObjectURL).toHaveBeenCalledExactlyOnceWith(source)
  })

  it('shows a download fallback when the media element reports an error', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="analysis-workflow" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    await loadedVideo()
    fireEvent.error(document.querySelector('video')!)
    expect(screen.getByRole('alert')).toHaveTextContent('Use Download video')
    expect(screen.getByRole('link', { name: 'Download video' })).toBeInTheDocument()
  })

  it('shows loading and aborts a pending fetch without creating a late Blob URL after Close', async () => {
    const pending = deferred<Response>()
    fetchClip.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="analysis-workflow" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(document.querySelector('video')).not.toHaveAttribute('src')
    const signal = fetchClip.mock.calls[0][1]!.signal!
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(signal.aborted).toBe(true)
    await act(async () => pending.resolve(clipResponse()))
    expect(createObjectURL).not.toHaveBeenCalled()
    expect(revokeObjectURL).not.toHaveBeenCalled()
    expect(document.querySelector('video')).toBeNull()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('ignores body completion after page unmount, even if the fetch mock ignores abort', async () => {
    const body = deferred<Blob>()
    const response = clipResponse()
    vi.spyOn(response, 'blob').mockReturnValue(body.promise)
    fetchClip.mockResolvedValueOnce(response)
    const user = userEvent.setup()
    const view = renderWithProviders(<TutorialWatch id="analysis-workflow" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    await waitFor(() => expect(response.blob).toHaveBeenCalled())
    view.unmount()
    expect(fetchClip.mock.calls[0][1]!.signal!.aborted).toBe(true)
    await act(async () => body.resolve(await clipResponse().blob()))
    expect(createObjectURL).not.toHaveBeenCalled()
    expect(revokeObjectURL).not.toHaveBeenCalled()
  })

  it.each([
    ['HTTP failure', () => Promise.resolve(new Response(null, { status: 404 }))],
    ['network failure', () => Promise.reject(new TypeError('offline'))],
    ['wrong file size', () => Promise.resolve(clipResponse(1))],
    ['wrong media type', () => Promise.resolve(clipResponse(TUTORIALS[0].bytes, 'text/html'))],
  ])('keeps the direct download fallback on %s', async (_name, result) => {
    fetchClip.mockImplementationOnce(result)
    const user = userEvent.setup()
    renderWithProviders(<TutorialWatch id="analysis-workflow" />)
    await user.click(screen.getByRole('button', { name: 'Watch tutorial' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Use Download video')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download video' })).toHaveAttribute('href', tutorialFile(TUTORIALS[0], 'mp4'))
    expect(createObjectURL).not.toHaveBeenCalled()
    expect(document.querySelector('video')).not.toHaveAttribute('src')
  })

  it('filters the library with every search word and hides it for no match', () => {
    const view = renderWithProviders(<VideoTutorials query="key metrics" />)
    expect(screen.getByRole('heading', { name: 'Analysis key metrics' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Start and add data' })).not.toBeInTheDocument()
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

  it('ships exact approved MP4s below 24 MiB with matching captions and posters', () => {
    const root = join(__dirname, '../../../public/tutorials')
    for (const tutorial of TUTORIALS) {
      const bytes = readFileSync(join(root, `${tutorial.id}.mp4`))
      expect(bytes.length).toBe(tutorial.bytes)
      expect(bytes.length).toBeLessThan(24 * 1024 ** 2)
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(tutorial.sha256)
      expect(tutorial.revision).toBe(tutorial.sha256.slice(0, 12))
      expect(readFileSync(join(root, `${tutorial.id}.vtt`), 'utf8')).toMatch(/^WEBVTT/)
      const poster = readFileSync(join(root, `${tutorial.id}.webp`))
      expect(poster.toString('ascii', 0, 4)).toBe('RIFF')
      expect(poster.toString('ascii', 8, 12)).toBe('WEBP')
    }
  })
})
