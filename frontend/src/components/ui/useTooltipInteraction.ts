import { useCallback, useEffect, useId, useRef, useState, type FocusEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from 'react'

const OPEN_EVENT = 'novaq-tooltip-open'
const LEAVE_GRACE_MS = 100

/** Shared pointer/keyboard ownership. Wrapper whitespace is never a trigger. */
export function useTooltipInteraction({ enabled = true, toggleOnClick = false } = {}) {
  const id = useId()
  const anchorRef = useRef<HTMLSpanElement>(null)
  const popupRef = useRef<HTMLSpanElement>(null)
  const [open, setOpen] = useState(false)
  const [portalHost, setPortalHost] = useState<HTMLElement | null>(null)
  const flags = useRef({ hovered: false, popupHovered: false, keyboard: false, pinned: false, pointerFocus: false, dismissed: false })
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const getTrigger = useCallback(() => {
    const child = anchorRef.current?.firstElementChild
    return child instanceof HTMLElement ? child : null
  }, [])
  const cancelLeave = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current)
    timer.current = null
  }, [])
  const dismiss = useCallback(() => {
    cancelLeave()
    flags.current = { hovered: false, popupHovered: false, keyboard: false, pinned: false, pointerFocus: false, dismissed: true }
    setOpen(false)
  }, [cancelLeave])
  const show = useCallback(() => {
    if (!enabled || flags.current.dismissed) return
    cancelLeave()
    setPortalHost(getTrigger()?.closest<HTMLDialogElement>('dialog[open]') ?? document.body)
    document.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }))
    setOpen(true)
  }, [cancelLeave, enabled, getTrigger, id])
  const leave = useCallback(() => {
    cancelLeave()
    timer.current = setTimeout(() => {
      timer.current = null
      const state = flags.current
      if (!state.hovered && !state.popupHovered && !state.keyboard && !state.pinned) dismiss()
    }, LEAVE_GRACE_MS)
  }, [cancelLeave, dismiss])

  useEffect(() => cancelLeave, [cancelLeave])
  useEffect(() => {
    function anotherOpened(event: Event) {
      if ((event as CustomEvent<string>).detail !== id) dismiss()
    }
    document.addEventListener(OPEN_EVENT, anotherOpened)
    return () => document.removeEventListener(OPEN_EVENT, anotherOpened)
  }, [dismiss, id])
  useEffect(() => { if (!enabled) dismiss() }, [dismiss, enabled])
  useEffect(() => {
    if (!open || !enabled) return
    function outside(event: Event) {
      if (event.target instanceof Node && !anchorRef.current?.contains(event.target) && !popupRef.current?.contains(event.target)) dismiss()
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      dismiss()
    }
    function scroll(event: Event) {
      if (event.target instanceof Node && popupRef.current?.contains(event.target)) return
      dismiss()
    }
    document.addEventListener('pointerdown', outside, true)
    document.addEventListener('focusin', outside, true)
    document.addEventListener('keydown', escape, true)
    window.addEventListener('scroll', scroll, true)
    window.addEventListener('resize', dismiss)
    window.visualViewport?.addEventListener('resize', dismiss)
    return () => {
      document.removeEventListener('pointerdown', outside, true)
      document.removeEventListener('focusin', outside, true)
      document.removeEventListener('keydown', escape, true)
      window.removeEventListener('scroll', scroll, true)
      window.removeEventListener('resize', dismiss)
      window.visualViewport?.removeEventListener('resize', dismiss)
    }
  }, [dismiss, enabled, open])

  const isTriggerTarget = (target: EventTarget | null) => target instanceof Node && Boolean(getTrigger()?.contains(target))
  return {
    open: enabled && open, anchorRef, popupRef, portalHost, getTrigger,
    triggerHandlers: {
      onPointerOver(event: ReactPointerEvent<HTMLSpanElement>) {
        if (event.pointerType === 'touch' || !isTriggerTarget(event.target) || isTriggerTarget(event.relatedTarget)) return
        flags.current.hovered = true
        flags.current.dismissed = false
        show()
      },
      onPointerOut(event: ReactPointerEvent<HTMLSpanElement>) {
        if (event.pointerType === 'touch' || !isTriggerTarget(event.target) || isTriggerTarget(event.relatedTarget)) return
        flags.current.hovered = false
        leave()
      },
      onPointerDownCapture(event: ReactPointerEvent<HTMLSpanElement>) {
        if (!isTriggerTarget(event.target)) return
        flags.current.pointerFocus = true
        flags.current.keyboard = false
      },
      onFocus(event: FocusEvent<HTMLSpanElement>) {
        if (!isTriggerTarget(event.target)) return
        flags.current.keyboard = !flags.current.pointerFocus
        flags.current.pointerFocus = false
        if (flags.current.keyboard) { flags.current.dismissed = false; show() }
      },
      onBlur(event: FocusEvent<HTMLSpanElement>) {
        if (!isTriggerTarget(event.target)) return
        flags.current.keyboard = false
        flags.current.pointerFocus = false
        if (flags.current.popupHovered && !event.relatedTarget) return
        dismiss()
      },
      onClickCapture(event: ReactMouseEvent<HTMLSpanElement>) {
        if (!isTriggerTarget(event.target)) return
        flags.current.pointerFocus = false
        if (!toggleOnClick) { dismiss(); return }
        if (flags.current.pinned) dismiss()
        else { flags.current.pinned = true; flags.current.dismissed = false; show() }
      },
    },
    popupHandlers: {
      onPointerEnter(event: ReactPointerEvent<HTMLSpanElement>) {
        if (event.pointerType === 'touch') return
        flags.current.popupHovered = true
        cancelLeave()
      },
      onPointerLeave(event: ReactPointerEvent<HTMLSpanElement>) {
        if (event.pointerType === 'touch') return
        flags.current.popupHovered = false
        leave()
      },
    },
  }
}

export type TooltipInteraction = ReturnType<typeof useTooltipInteraction>
