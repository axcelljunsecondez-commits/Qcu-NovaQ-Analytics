import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { queueingLessonAsset, videoTime, type QueueingLesson } from '../../lib/queueingLessons'

/** Mirrors the existing tutorial Blob lifecycle; custom controls remain outside the captioned picture. */
export function LessonPlayer({ lesson }: { lesson: QueueingLesson }) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const player = useRef<HTMLDivElement>(null)
  const pendingPlay = useRef(false)
  const [request, setRequest] = useState(0)
  const [source, setSource] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [playHint, setPlayHint] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(lesson.seconds)

  useEffect(() => {
    if (request === 0) return
    const node = video.current
    const controller = new AbortController()
    let active = true
    let objectUrl: string | undefined
    setLoading(true)
    setError(false)
    setSource(undefined)
    void (async () => {
      try {
        const response = await fetch(queueingLessonAsset(lesson, 'mp4'), { signal: controller.signal })
        if (!response.ok) throw new Error('Lesson download failed')
        const blob = await response.blob()
        if (blob.size !== lesson.bytes || blob.type !== 'video/mp4' || blob.size >= 25 * 1024 ** 2) throw new Error('Unexpected lesson file')
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setSource(objectUrl)
        setLoading(false)
      } catch {
        if (active && !controller.signal.aborted) {
          pendingPlay.current = false
          setLoading(false)
          setError(true)
        }
      }
    })()
    return () => {
      active = false
      controller.abort()
      node?.pause()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [lesson, request])

  function togglePlay() {
    const node = video.current
    if (!node || loading) return
    setPlayHint(false)
    if (!source || error) {
      pendingPlay.current = true
      setRequest((value) => value + 1)
    } else if (!node.paused) node.pause()
    else {
      if (node.ended) node.currentTime = 0
      void node.play().catch(() => setPlayHint(true))
    }
  }

  function startRequestedPlayback() {
    if (!pendingPlay.current || !video.current) return
    pendingPlay.current = false
    void video.current.play().catch(() => setPlayHint(true))
  }

  function seek(seconds: number) {
    if (!source || !video.current) return
    video.current.currentTime = Math.min(duration, Math.max(0, seconds))
    setPosition(video.current.currentTime)
  }

  return <div className="queueing-lesson-media">
    <div className="queueing-lesson-player" ref={player}>
      <div className="queueing-lesson-picture">
        <video ref={video} src={source} playsInline preload="none" poster={queueingLessonAsset(lesson, 'webp')}
          aria-label={t(`queueing101.${lesson.id}.title`)} aria-busy={loading}
          onCanPlay={startRequestedPlayback} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)} onError={() => { if (source) setError(true) }}
          onTimeUpdate={() => setPosition(video.current?.currentTime ?? 0)}
          onLoadedMetadata={() => { if (video.current && Number.isFinite(video.current.duration)) setDuration(video.current.duration) }}>
          <track kind="captions" src={queueingLessonAsset(lesson, 'vtt')} srcLang="en" label="English" />
        </video>
        {!source && <button type="button" className="queueing-lesson-cover" disabled={loading}
          aria-label={t('queueing101.play_named', { title: t(`queueing101.${lesson.id}.title`) })} onClick={togglePlay}>
          <span aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m9 5 10 7-10 7Z" /></svg></span>
        </button>}
      </div>
      <div className="queueing-lesson-controls" role="group" aria-label={t('queueing101.controls')}>
        <button type="button" className="queueing-play-button" onClick={togglePlay} disabled={loading}
          aria-pressed={playing}>{t(loading ? 'common.loading' : playing ? 'queueing101.pause' : 'queueing101.play')}</button>
        <button type="button" onClick={() => seek(position - 10)} disabled={!source} aria-label={t('queueing101.back_ten')}>−10 s</button>
        <label className="queueing-seek"><span className="queueing-sr-only">{t('queueing101.position')}</span>
          <input type="range" min="0" max={duration} step="0.1" value={Math.min(position, duration)} disabled={!source}
            onChange={(event) => seek(Number(event.target.value))} />
          <span className="queueing-video-time" aria-live="off">{videoTime(position)} / {videoTime(Math.ceil(duration))}</span>
        </label>
        <label><span className="queueing-sr-only">{t('queueing101.speed')}</span>
          <select defaultValue="1" onChange={(event) => { if (video.current) { video.current.playbackRate = Number(event.target.value); video.current.preservesPitch = true } }}>
            <option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option>
          </select>
        </label>
        <button type="button" onClick={() => { if (video.current) { video.current.muted = !muted; setMuted(!muted) } }}
          aria-pressed={muted}>{t(muted ? 'queueing101.sound_off' : 'queueing101.sound_on')}</button>
        {document.fullscreenEnabled && <button type="button" onClick={() => {
          const action = document.fullscreenElement ? document.exitFullscreen() : player.current?.requestFullscreen()
          void action?.catch(() => setPlayHint(true))
        }}>{t('queueing101.fullscreen')}</button>}
      </div>
    </div>
    {loading && <p className="form-hint" role="status">{t('queueing101.loading')}</p>}
    {playHint && <p className="form-hint" role="status">{t('queueing101.press_play')}</p>}
    {error && <p className="alert alert-warn" role="alert">{t('queueing101.video_error')}</p>}
    <div className="queueing-lesson-downloads">
      <a href={queueingLessonAsset(lesson, 'mp4')} download={`${lesson.id}.mp4`}>{t('tutorials.download_video')}</a>
      <a href={queueingLessonAsset(lesson, 'vtt')} download={`${lesson.id}.vtt`}>{t('tutorials.download_captions')}</a>
    </div>
    <details className="queueing-lesson-transcript"><summary>{t('queueing101.transcript')}</summary>
      {lesson.chapters.map((chapter) => <p key={chapter.seconds}><strong>{videoTime(chapter.seconds)} · {chapter.title}</strong><br />{chapter.text}</p>)}
    </details>
  </div>
}
