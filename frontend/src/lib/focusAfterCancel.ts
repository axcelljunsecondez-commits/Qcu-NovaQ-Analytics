/**
 * Where keyboard focus goes after a replacement confirmation is cancelled (D2, N1): the primary
 * action when it can be used; otherwise the first enabled control in its card; otherwise the card.
 */
export function focusAfterCancel(primary: HTMLButtonElement | null, card: HTMLElement | null): void {
  if (primary && !primary.disabled) { primary.focus(); return }
  const next = card?.querySelector<HTMLElement>(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])',
  )
  const target = next ?? card
  target?.focus()
}
