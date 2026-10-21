import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { TUTORIALS, tutorialDuration, tutorialFile, tutorialSteps, type Tutorial, type TutorialId } from '../../lib/tutorials'

function Player({ tutorial }: { tutorial: Tutorial }) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState(false)
  const [source, setSource] = useState<string>()
  useEffect(() => {
    const node = video.current
    const controller = new AbortController()
    let active = true
    let objectUrl: string | undefined
    // Pages may ignore Range requests. A local Blob gives native controls a
    // seekable file without an extra server or player dependency.
    void (async () => {
      try {
        const response = await fetch(tutorialFile(tutorial, 'mp4'), { signal: controller.signal })
        if (!response.ok) throw new Error('Tutorial download failed')
        const blob = await response.blob()
        if (blob.size !== tutorial.bytes || blob.size >= 25 * 1024 ** 2 || blob.type !== 'video/mp4') {
          throw new Error('Unexpected tutorial file')
        }
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setSource(objectUrl)
      } catch {
        if (active && !controller.signal.aborted) setError(true)
      }
    })()
    return () => {
      active = false
      controller.abort()
      node?.pause()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [tutorial])
  return <>
    <video ref={video} controls playsInline preload="metadata" poster={tutorialFile(tutorial, 'webp')}
      src={source} aria-busy={!source && !error} aria-label={t(`tutorials.${tutorial.id}.title`)} onError={() => setError(true)} />
    {!source && !error && <p role="status" className="form-hint">{t('common.loading')}</p>}
    <div className="tutorial-downloads">
      <a className="btn-ghost" href={tutorialFile(tutorial, 'mp4')} download={`${tutorial.id}.mp4`}>{t('tutorials.download_video')}</a>
      <a href={tutorialFile(tutorial, 'vtt')} download={`${tutorial.id}.vtt`}>{t('tutorials.download_captions')}</a>
    </div>
    {error && <p role="alert" className="alert alert-warn">{t('tutorials.video_error')}</p>}
    <details className="tutorial-steps"><summary>{t('tutorials.read_steps')}</summary>
      <ol>{tutorialSteps(tutorial.id).map((step) => <li key={step.time}><span className="tutorial-time">{step.time}</span>{step.caption}</li>)}</ol>
    </details>
  </>
}

/** Optional help only: no form, query, run, or analysis state is changed. */
export function TutorialWatch({ id, compact = false }: { id: TutorialId; compact?: boolean }) {
  const { t } = useTranslation()
  const tutorial = TUTORIALS.find((item) => item.id === id)!
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const close = useRef<HTMLButtonElement>(null)
  const wasOpen = useRef(false)
  const titleId = useId()
  const metaId = useId()

  useEffect(() => {
    const node = dialog.current
    if (!node) return
    if (open) {
      if (!node.open) node.showModal()
      wasOpen.current = true
      close.current?.focus()
    } else {
      if (node.open) node.close()
      if (wasOpen.current) trigger.current?.focus()
      wasOpen.current = false
    }
  }, [open])

  return <>
    <button ref={trigger} type="button" className="btn-ghost tutorial-watch" onClick={() => setOpen(true)}
      aria-label={compact ? t('tutorials.watch_named', { title: t(`tutorials.${id}.title`) }) : undefined}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7Z" /></svg>
      {t(compact ? 'tutorials.watch' : 'tutorials.watch_tutorial')}
    </button>
    <dialog ref={dialog} className="tutorial-dialog" aria-labelledby={titleId} aria-describedby={metaId}
      onCancel={(event) => { event.preventDefault(); setOpen(false) }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return
        const rect = event.currentTarget.getBoundingClientRect()
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) setOpen(false)
      }}>
      {open && <>
        <header className="tutorial-dialog-heading">
          <div><h2 id={titleId} className="section-title">{t(`tutorials.${id}.title`)}</h2>
            <p id={metaId} className="form-hint">{tutorialDuration(tutorial)} · {t('tutorials.language')}</p></div>
          <button ref={close} type="button" className="btn-ghost" onClick={() => setOpen(false)}>{t('tutorials.close')}</button>
        </header>
        <Player key={tutorial.id} tutorial={tutorial} />
        <p className="form-hint tutorial-example-note">{t('tutorials.example_note')}</p>
      </>}
    </dialog>
  </>
}
