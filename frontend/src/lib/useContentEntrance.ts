import { useEffect, useRef, type RefObject } from 'react'
import { useLocation } from 'react-router-dom'

interface EntranceOptions {
  animateInitial?: boolean
  /** A panel must change as well as the explicit navigation trigger. Data refreshes alone never animate. */
  contentKey?: string | null
}

/** Presentation only: animate an existing element without keys, remounts or hidden fallback styles. */
export function useContentEntrance<T extends HTMLElement>(trigger: string | null, duration = 220, { animateInitial = true, contentKey = trigger }: EntranceOptions = {}): RefObject<T | null> {
  const ref = useRef<T>(null)
  const previous = useRef<{ trigger: string | null; contentKey: string | null } | null>(null)

  useEffect(() => {
    const prior = previous.current
    previous.current = { trigger, contentKey }
    if (!animateInitial && (!prior || prior.trigger === trigger || prior.contentKey === contentKey)) return
    const element = ref.current
    if (!element || typeof element.animate !== 'function') return
    const motion = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
    if (motion?.matches) return
    const animation = element.animate(
      [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration, easing: 'cubic-bezier(.16,1,.3,1)' },
    )
    const onMotionChange = (event: MediaQueryListEvent) => { if (event.matches) animation.cancel() }
    motion?.addEventListener?.('change', onMotionChange)
    return () => {
      motion?.removeEventListener?.('change', onMotionChange)
      animation.cancel()
    }
  }, [trigger, contentKey, duration, animateInitial])

  return ref
}

/** Path navigation only. Query changes, replay time and hash-only jumps retain page context. */
export function usePageContent<T extends HTMLElement>(scrollContainer?: RefObject<HTMLElement | null>): RefObject<T | null> {
  const { pathname, hash } = useLocation()
  const ref = useContentEntrance<T>(pathname)
  const previousPath = useRef<string | null>(null)

  useEffect(() => {
    if (previousPath.current === pathname) return
    previousPath.current = pathname
    if (hash) return
    const target = scrollContainer?.current ?? ref.current
    const containers = new Set([document.scrollingElement, document.documentElement, document.body, target])
    for (const container of containers) {
      if (!(container instanceof HTMLElement)) continue
      const behavior = container.style.scrollBehavior
      container.style.scrollBehavior = 'auto'
      container.scrollTop = 0
      container.scrollLeft = 0
      container.style.scrollBehavior = behavior
    }
    target?.focus({ preventScroll: true })
  }, [pathname, hash, scrollContainer, ref])

  return ref
}
