import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

interface ExpandableSlidesProps {
  id?: string
  title: string
  description: string
  open: boolean
  onOpenChange: (open: boolean) => void
  slides: ReadonlyArray<{ id: string; label: string; content: ReactNode }>
  className?: string
  footer?: ReactNode
}

export function Chevron({ direction }: { direction: 'left' | 'right' | 'down' }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={direction === 'left' ? 'm15 6-6 6 6 6' : direction === 'right' ? 'm9 6 6 6-6 6' : 'm6 9 6 6 6-6'} /></svg>
}

/** Presentation only. Slides retain their intrinsic maximum height; navigation never scrolls or moves focus. */
export function ExpandableSlides({ id, title, description, open, onOpenChange, slides, className = '', footer }: ExpandableSlidesProps) {
  const { t } = useTranslation()
  const uniqueId = useId()
  const baseId = id ?? uniqueId
  const [index, setIndex] = useState(0)
  const current = useRef(0)
  const nodes = useRef<Array<HTMLElement | null>>([])
  const animations = useRef<Animation[]>([])
  useEffect(() => () => animations.current.forEach((animation) => animation.cancel()), [])

  function navigate(direction: -1 | 1) {
    if (slides.length < 2) return
    const previousIndex = current.current
    const nextIndex = (previousIndex + direction + slides.length) % slides.length
    const previous = nodes.current[previousIndex]
    const next = nodes.current[nextIndex]
    const previousStyle = previous ? getComputedStyle(previous) : undefined
    const nextStyle = next ? getComputedStyle(next) : undefined
    const outgoing = { opacity: previousStyle?.opacity ?? '1', transform: previousStyle?.transform ?? 'none' }
    const incoming = { opacity: nextStyle?.opacity ?? '0', transform: nextStyle?.transform ?? 'none' }
    animations.current.forEach((animation) => animation.cancel())
    animations.current = []
    current.current = nextIndex
    setIndex(nextIndex)
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion || !previous?.animate || !next?.animate) return
    const easing = 'cubic-bezier(.22,1,.36,1)'
    animations.current = [
      previous.animate([
        { visibility: 'visible', ...outgoing },
        { visibility: 'visible', opacity: 0, transform: `translateX(${-direction * 22}px)` },
      ], { duration: 320, easing }),
      next.animate([
        { visibility: 'visible', opacity: incoming.opacity, transform: Number(incoming.opacity) > .01 ? incoming.transform : `translateX(${direction * 22}px)` },
        { visibility: 'visible', opacity: 1, transform: 'translateX(0px)' },
      ], { duration: 420, easing }),
    ]
  }

  return <section className={`home-guide ${open ? 'is-open' : ''} ${className}`} data-guide={id}>
    <h2 className="home-guide-heading">
      <button id={`${baseId}-trigger`} type="button" className="home-guide-toggle" aria-expanded={open}
        aria-controls={`${baseId}-panel`} aria-labelledby={`${baseId}-title`} aria-describedby={`${baseId}-description`} onClick={() => onOpenChange(!open)}>
        <span><strong id={`${baseId}-title`}>{title}</strong><small id={`${baseId}-description`}>{description}</small></span><Chevron direction="down" />
      </button>
    </h2>
    <div id={`${baseId}-panel`} className="home-guide-panel" role="region" aria-labelledby={`${baseId}-trigger`}
      aria-hidden={!open} inert={!open}>
      <div className="home-guide-inner"><div className="home-guide-body">
        <div className="home-guide-slides" role="group" aria-label={title}>
          {slides.map((slide, slideIndex) => <article key={slide.id} ref={(node) => { nodes.current[slideIndex] = node }}
            className="home-guide-slide" data-active={slideIndex === index} aria-hidden={slideIndex !== index}
            inert={slideIndex !== index} aria-label={slide.label}>{slide.content}</article>)}
        </div>
        {footer}
        <div className="home-guide-controls">
          <button type="button" className="btn-ghost" aria-label={t('queueing101.previous_named', { title })} onClick={() => navigate(-1)}><Chevron direction="left" />{t('queueing101.previous')}</button>
          <span aria-live="polite" aria-atomic="true">{t('queueing101.slide_status', { current: index + 1, total: slides.length })}</span>
          <button type="button" className="btn-ghost" aria-label={t('queueing101.next_named', { title })} onClick={() => navigate(1)}>{t('queueing101.next')}<Chevron direction="right" /></button>
        </div>
      </div></div>
    </div>
  </section>
}
