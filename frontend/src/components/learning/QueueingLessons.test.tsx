import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { StrictMode } from 'react'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { renderWithProviders, testI18n } from '../../test/test-utils'
import { matchingQueueingLessons, QUEUEING_LESSONS, queueingLessonAsset } from '../../lib/queueingLessons'
import { QueueingLessons } from './QueueingLessons'

vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))
const fetchClip = vi.fn<typeof fetch>()
const pause = vi.fn()
const play = vi.fn(async () => undefined)
const createUrl = vi.fn(() => 'blob:https://novaq.test/queueing-lesson')
const revokeUrl = vi.fn()
const descriptors = new Map<string, PropertyDescriptor | undefined>()
const nativeDescriptors = new Map<string, PropertyDescriptor | undefined>()
function response(bytes: number, type = 'video/mp4') { return new Response(new Uint8Array(bytes), { headers: { 'Content-Type': type } }) }

beforeAll(() => {
  for (const key of ['showModal', 'close']) descriptors.set(key, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, key))
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', '') } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open') } })
  for (const key of ['createObjectURL', 'revokeObjectURL']) nativeDescriptors.set(key, Object.getOwnPropertyDescriptor(URL, key))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createUrl })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeUrl })
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause)
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(play)
})
beforeEach(() => {
  fetchClip.mockReset(); pause.mockClear(); play.mockClear(); createUrl.mockClear(); revokeUrl.mockClear()
  fetchClip.mockImplementation(async (input) => {
    const item = QUEUEING_LESSONS.find((lesson) => queueingLessonAsset(lesson, 'mp4') === String(input))
    if (!item) throw Error('Unexpected fixture URL')
    return response(item.bytes)
  })
  vi.stubGlobal('fetch', fetchClip)
})
afterEach(() => vi.unstubAllGlobals())
afterAll(() => {
  for (const [key, value] of descriptors) { if (value) Object.defineProperty(HTMLDialogElement.prototype, key, value); else Reflect.deleteProperty(HTMLDialogElement.prototype, key) }
  for (const [key, value] of nativeDescriptors) { if (value) Object.defineProperty(URL, key, value); else Reflect.deleteProperty(URL, key) }
  vi.restoreAllMocks()
})

describe('Queueing lessons (media/native dialog are explicitly stubbed in JSDOM)', () => {
  it('does not download or play a clip until requested', () => {
    renderWithProviders(<QueueingLessons />)
    expect(document.querySelector('video')).not.toHaveAttribute('src')
    expect(document.querySelector('video')).not.toHaveAttribute('autoplay')
    expect(fetchClip).not.toHaveBeenCalled()
    expect(play).not.toHaveBeenCalled()
    expect(screen.getByText(en['queueing101.language'])).toBeInTheDocument()
  })

  it.each(QUEUEING_LESSONS)('loads the full $id clip only after Play and preserves download/caption mapping', async (lesson) => {
    const user = userEvent.setup()
    renderWithProviders(<QueueingLessons />)
    await user.click(within(screen.getByRole('group', { name: en['queueing101.choose'] })).getByRole('button', { name: new RegExp(en[`queueing101.${lesson.id}.title`]) }))
    await user.click(screen.getByRole('button', { name: 'Play' }))
    const node = document.querySelector('video')!
    await waitFor(() => expect(node).toHaveAttribute('src', expect.stringMatching(/^blob:/)))
    expect(fetchClip).toHaveBeenCalledExactlyOnceWith(queueingLessonAsset(lesson, 'mp4'), { signal: expect.any(AbortSignal) })
    expect(createUrl).toHaveBeenCalledWith(expect.objectContaining({ size: lesson.bytes, type: 'video/mp4' }))
    fireEvent.canPlay(node);fireEvent.canPlay(node)
    expect(play).toHaveBeenCalledOnce()
    expect(screen.getByRole('link', { name: 'Download video' })).toHaveAttribute('href', queueingLessonAsset(lesson, 'mp4'))
    expect(screen.getByRole('link', { name: 'Download captions' })).toHaveAttribute('href', queueingLessonAsset(lesson, 'vtt'))
    expect(node).not.toHaveAttribute('controls')
  })

  it('aborts a pending download and ignores late body completion when switching lessons', async () => {
    let finish!: (value: Blob) => void
    const body = new Promise<Blob>((resolve) => { finish = resolve })
    const clipResponse = response(QUEUEING_LESSONS[0].bytes)
    vi.spyOn(clipResponse, 'blob').mockReturnValue(body)
    fetchClip.mockResolvedValue(clipResponse)
    const user = userEvent.setup()
    renderWithProviders(<QueueingLessons />)
    await user.click(screen.getByRole('button', { name: 'Play' }))
    await waitFor(() => expect(clipResponse.blob).toHaveBeenCalled())
    const signal = fetchClip.mock.calls[0][1]!.signal!
    await user.click(screen.getByRole('button', { name: /What your team should record/ }))
    expect(signal.aborted).toBe(true)
    await act(async () => finish(await response(QUEUEING_LESSONS[0].bytes).blob()))
    expect(createUrl).not.toHaveBeenCalled()
    expect(document.querySelector('video')).not.toHaveAttribute('src')
    expect(document.querySelector('video')).toHaveAttribute('poster', queueingLessonAsset(QUEUEING_LESSONS[1], 'webp'))
    expect(play).not.toHaveBeenCalled()
  })

  it('pauses, aborts and revokes the loaded source on replacement, including StrictMode', async () => {
    const user = userEvent.setup()
    const view = renderWithProviders(<StrictMode><QueueingLessons /></StrictMode>)
    await user.click(screen.getByRole('button', { name: 'Play' }))
    await waitFor(() => expect(document.querySelector('video')).toHaveAttribute('src', expect.stringMatching(/^blob:/)))
    const signal = fetchClip.mock.calls[0][1]!.signal!
    await user.click(screen.getByRole('button', { name: /What your team should record/ }))
    expect(signal.aborted).toBe(true)
    expect(pause).toHaveBeenCalled()
    expect(revokeUrl).toHaveBeenCalledExactlyOnceWith('blob:https://novaq.test/queueing-lesson')
    view.unmount()
  })

  it.each([[7, 'video/mp4'], [QUEUEING_LESSONS[0].bytes, 'text/html']])('rejects a mismatched body (%s, %s)', async (bytes, type) => {
    fetchClip.mockResolvedValue(response(Number(bytes), String(type)))
    const user = userEvent.setup()
    renderWithProviders(<QueueingLessons />)
    await user.click(screen.getByRole('button', { name: 'Play' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(en['queueing101.video_error'])
    expect(createUrl).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Download video' })).toBeInTheDocument()
  })

  it('keeps the checklist separate from upload templates and restores focus', async () => {
    const user = userEvent.setup()
    renderWithProviders(<QueueingLessons />)
    const trigger = screen.getByRole('button', { name: en['queueing101.checklist'] })
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: en['queueing101.checklist_title'] })
    expect(within(dialog).getByText(en['queueing101.field_log_note'])).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: en['queueing101.customer_sheet'] })).toHaveAttribute('href', '/queueing101/customer-field-log.csv')
    expect(within(dialog).getByRole('button', { name: 'Close' })).toHaveFocus()
    fireEvent(dialog, new Event('cancel', { bubbles: true, cancelable: true }))
    await waitFor(() => expect(trigger).toHaveFocus())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('filters by all search terms, including the spelled-out parameter names', () => {
    renderWithProviders(<QueueingLessons query="theta variance" />)
    expect(matchingQueueingLessons('theta variance', testI18n().t).map((item) => item.id)).toEqual(['part2'])
    expect(within(screen.getByRole('group', { name: en['queueing101.choose'] })).getByRole('button', { name: /What your team should record/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Follow Ben/ })).not.toBeInTheDocument()
  })

  it('has symmetric localized keys and unchanged approved full-media hashes', () => {
    const keys = Object.keys(en).filter((key) => key.startsWith('queueing101.')).sort()
    expect(keys).toEqual(Object.keys(tl).filter((key) => key.startsWith('queueing101.')).sort())
    for (const key of keys) expect((en[key as keyof typeof en].match(/{{[^}]+}}/g) ?? []).sort()).toEqual((tl[key as keyof typeof tl].match(/{{[^}]+}}/g) ?? []).sort())
    const pinned = ['14076de82423998b05fd004368f8ff222d11cf8e896a7e6791c35b61fb7a7ade', '9dc12e479c57155e82fbcb10b507b1cc5e98d31ecc076f0608abd089186b4804']
    QUEUEING_LESSONS.forEach((lesson, index) => {
      const bytes = readFileSync(join(__dirname, '../../../public/queueing101', `${lesson.id}.mp4`))
      expect(bytes.length).toBe(lesson.bytes)
      expect(bytes.length).toBeLessThan(25 * 1024 ** 2)
      expect(bytes.toString('ascii', 4, 8)).toBe('ftyp')
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(pinned[index])
      expect(lesson.sha256).toBe(pinned[index])
    })
    for (const name of ['customer-field-log.csv', 'counter-availability-log.csv']) expect(readFileSync(join(__dirname, '../../../public/queueing101', name), 'utf8').trim().split(/\r?\n/)).toHaveLength(1)
  })
})
