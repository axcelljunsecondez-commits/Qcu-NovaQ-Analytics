// Captures the annotated Help screenshots (plan U10, spec 2026-10-14-u10-help-screenshots).
// Drives a local headless Edge or Chrome through the DevTools protocol (Node 22+ has WebSocket),
// signs in to a LOCAL NovaQ dev app with test credentials and writes
// public/help-images/<lang>/<topic>.webp. Run only against a scratch database with clearly
// synthetic data: the images are public.
//
//   NOVAQ_HELP_EMAIL=... NOVAQ_HELP_PASSWORD=... NOVAQ_HELP_ANALYSIS=10 \
//     node scripts/help-screenshots.mjs [http://localhost:5174]
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const BASE = process.argv[2] ?? 'http://localhost:5174'
const EMAIL = process.env.NOVAQ_HELP_EMAIL
const PASSWORD = process.env.NOVAQ_HELP_PASSWORD
const ANALYSIS = Number(process.env.NOVAQ_HELP_ANALYSIS)
const PORT = 9333
const WIDTH = 1280
// Tall enough that every marked region fits without scrolling: capturing beyond the viewport
// re-lays out the page and moves the fixed sidebar over the content.
const HEIGHT = 3000
const MAX_CLIP_HEIGHT = 1300
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'help-images')

if (!['localhost', '127.0.0.1', '[::1]'].includes(new URL(BASE).hostname)) {
  throw new Error(`Refusing ${BASE}: screenshots are taken from a local dev app only.`)
}
if (!EMAIL || !PASSWORD || !Number.isInteger(ANALYSIS) || ANALYSIS < 1) {
  throw new Error('Set NOVAQ_HELP_EMAIL, NOVAQ_HELP_PASSWORD and NOVAQ_HELP_ANALYSIS.')
}

// One image per guide. Each mark is a selector (and optionally the ancestor to outline); the
// numbers follow the list order and match help.guide.<topic>.figure.mark_<n> in the locales.
// `include` widens the picture to unmarked elements such as a section heading.
const SHOTS = [
  { topic: 'start', path: '/analyses/new', marks: [
    { sel: '#analysis-name', up: '.form-field' },
    { sel: 'fieldset.structure-choice' },
    { sel: 'main button.btn-primary' },
  ] },
  { topic: 'data', path: `/analyses/${ANALYSIS}/data`, marks: [
    { sel: 'li.setup-step:nth-of-type(1) > .card' },
    { sel: 'fieldset.setup-purpose' },
    { sel: 'li.setup-step:nth-of-type(2) > .card > button' },
  ] },
  { topic: 'results', path: `/results?analysis=${ANALYSIS}`, marks: [
    { sel: 'section.key-result:has(#kr-recorded-label)' },
    { sel: 'section.key-result:has(#kr-estimated-label)' },
    { sel: 'section.card:has(#busy-strip-title)' },
  ] },
  { topic: 'plans', path: `/analyses/${ANALYSIS}/plans`, click: '.optimize-page button.button-primary',
    waitFor: '.optimize-page table', marks: [
      { sel: '#opt-util', up: '.card' },
      { sel: '.optimize-page button.button-primary' },
      { sel: '#opt-scenario', up: '.card' },
    ] },
  { topic: 'simulation', path: `/simulation/results?analysis=${ANALYSIS}&plan=suggested`, include: ['.run-switch'], marks: [
    { sel: 'nav.workspace-tabs' },
    { sel: '.continuous-section [data-testid=closing-rule]' },
    { sel: '.continuous-section .run-bar button.btn-primary' },
    { sel: '.continuous-section h3.kpi-label', up: '.card' },
  ] },
  { topic: 'checks', path: `/simulation/checks?analysis=${ANALYSIS}&plan=suggested`, include: ['#legacy-decision-title'], marks: [
    { sel: '[data-testid=decision-plain]', up: '.alert' },
    { sel: '[data-testid=full-day-periods]' },
    { sel: 'section.card:has(#legacy-decision-title) button.btn-primary' },
  ] },
  { topic: 'downloads', path: `/reports?analysis=${ANALYSIS}`, marks: [
    { sel: '[data-testid=report-stamp]' },
    { sel: '[data-testid=report-card-pdf]' },
    { sel: '[data-testid=report-card-excel]' },
    { sel: '[data-testid=report-card-data]' },
  ] },
]

function browserPath() {
  const candidates = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ]
  const found = candidates.find((path) => existsSync(path))
  if (!found) throw new Error('No local Edge or Chrome found.')
  return found
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function devtoolsPage() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })
      if (response.ok) return (await response.json()).webSocketDebuggerUrl
    } catch {
      // The browser is still starting.
    }
    await sleep(200)
  }
  throw new Error('The browser did not open its DevTools port.')
}

function connect(url) {
  const socket = new WebSocket(url)
  let next = 0
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id === undefined || !pending.has(message.id)) return
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(message.error.message))
    else resolve(message.result)
  })
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    next += 1
    pending.set(next, { resolve, reject })
    socket.send(JSON.stringify({ id: next, method, params }))
  })
  return new Promise((resolve) => socket.addEventListener('open', () => resolve({ send, close: () => socket.close() })))
}

async function evaluate(cdp, expression) {
  const { result, exceptionDetails } = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? exceptionDetails.text)
  return result.value
}

async function waitFor(cdp, selectors) {
  const list = JSON.stringify(selectors)
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (await evaluate(cdp, `${list}.every((s) => document.querySelector(s))`)) return
    await sleep(200)
  }
  throw new Error(`Timed out waiting for ${selectors.join(', ')}`)
}

async function open(cdp, path) {
  await cdp.send('Page.navigate', { url: BASE + path })
  await sleep(500)
}

// Draws numbered outlines over the marked elements and returns the clip around them.
function annotate(marks, include = []) {
  return `(() => {
    document.querySelectorAll('[data-help-shot]').forEach((node) => node.remove())
    window.scrollTo(0, 0)
    const marks = ${JSON.stringify(marks)}
    const boxes = marks.map(({ sel, up }) => {
      const found = document.querySelector(sel)
      if (!found) throw new Error('Missing mark ' + sel)
      const node = up ? found.closest(up) : found
      const rect = node.getBoundingClientRect()
      return { left: rect.left, top: rect.top, width: rect.width, height: rect.height }
    })
    boxes.forEach((box, index) => {
      const outline = document.createElement('div')
      outline.dataset.helpShot = ''
      Object.assign(outline.style, { position: 'fixed', left: box.left - 4 + 'px', top: box.top - 4 + 'px',
        width: box.width + 8 + 'px', height: box.height + 8 + 'px', border: '3px solid #c2410c',
        borderRadius: '8px', pointerEvents: 'none', zIndex: 10000, boxSizing: 'border-box' })
      const badge = document.createElement('div')
      badge.dataset.helpShot = ''
      badge.textContent = String(index + 1)
      Object.assign(badge.style, { position: 'fixed', left: Math.max(2, box.left - 16) + 'px',
        top: Math.max(2, box.top - 16) + 'px', width: '28px', height: '28px', borderRadius: '50%',
        background: '#c2410c', color: '#ffffff', font: '700 16px/28px system-ui, sans-serif',
        textAlign: 'center', boxShadow: '0 0 0 2px #ffffff', pointerEvents: 'none', zIndex: 10001 })
      document.body.append(outline, badge)
    })
    const extra = ${JSON.stringify(include)}.map((sel) => document.querySelector(sel).getBoundingClientRect())
    const all = [...boxes, ...extra]
    const content = document.querySelector('main .page-stack, main .setup-page, main').getBoundingClientRect()
    const sidebar = document.querySelector('aside.sidebar')
    const top = Math.max(0, Math.min(...all.map((b) => b.top)) - 34)
    const bottom = Math.max(...all.map((b) => b.top + b.height)) + 20
    const left = Math.max(sidebar ? sidebar.getBoundingClientRect().right : 0, content.left - 24)
    // Whole pixels, so the image size equals the clip (help figure sizes are checked against it).
    const x = Math.floor(left)
    const y = Math.floor(top)
    return { x, y, width: Math.floor(Math.min(content.width + 48, innerWidth - x)),
      height: Math.floor(Math.min(bottom - y, ${MAX_CLIP_HEIGHT})) }
  })()`
}

async function main() {
  const profile = mkdtempSync(join(tmpdir(), 'novaq-help-shots-'))
  const browser = spawn(browserPath(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', `--window-size=${WIDTH},${HEIGHT}`, 'about:blank'],
  { stdio: 'ignore' })
  const sizes = {}
  try {
    const cdp = await connect(await devtoolsPage())
    await cdp.send('Page.enable')
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false })
    await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] })
    await open(cdp, '/login')
    const status = await evaluate(cdp, `fetch('/api/auth/login', { method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: ${JSON.stringify(EMAIL)}, password: ${JSON.stringify(PASSWORD)} }) }).then((r) => r.status)`)
    if (status !== 200) throw new Error(`Sign-in failed with HTTP ${status}`)
    for (const lang of ['en', 'tl']) {
      await evaluate(cdp, `localStorage.setItem('novaq_lang', '${lang}'); localStorage.setItem('novaq_theme', 'light')`)
      mkdirSync(join(OUT, lang), { recursive: true })
      for (const shot of SHOTS) {
        await open(cdp, shot.path)
        await waitFor(cdp, shot.click ? [shot.click] : shot.marks.map((mark) => mark.sel))
        if (shot.click) {
          await evaluate(cdp, `document.querySelector(${JSON.stringify(shot.click)}).click()`)
          await waitFor(cdp, [shot.waitFor, ...shot.marks.map((mark) => mark.sel)])
        }
        await sleep(1500)
        await evaluate(cdp, 'document.fonts.ready.then(() => true)')
        const clip = await evaluate(cdp, annotate(shot.marks, shot.include))
        const { data } = await cdp.send('Page.captureScreenshot', { format: 'webp', quality: 90,
          clip: { ...clip, scale: 1 } })
        writeFileSync(join(OUT, lang, `${shot.topic}.webp`), Buffer.from(data, 'base64'))
        sizes[`${lang}/${shot.topic}`] = [clip.width, clip.height]
        console.log(`${lang}/${shot.topic}.webp`, clip.width, 'x', clip.height)
      }
    }
    cdp.close()
  } finally {
    browser.kill()
    await sleep(500)
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 })
  }
  return sizes
}

console.log(JSON.stringify(await main()))
