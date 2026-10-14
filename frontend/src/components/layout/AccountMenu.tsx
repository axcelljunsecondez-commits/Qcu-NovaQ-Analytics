import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { setLang } from '../../lib/i18n'
import { initialsFor } from '../../lib/initials'
import { Tooltip } from '../ui/Tooltip'

function menuItems(menu: HTMLElement | null): HTMLElement[] {
  return Array.from(menu?.querySelectorAll<HTMLElement>('[role="menuitem"], [role="menuitemradio"]') ?? [])
}

// Account button and menu (spec §7.3, D10): email, Settings, Language, Get help, Log out.
// Menu-button pattern: arrows/Home/End move focus; Escape, Tab and outside
// click close the menu, and Escape or outside click return focus to the button.
export function AccountMenu({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const buttonId = useId()
  const language = i18n.language === 'tl' ? 'tl' : 'en'

  useEffect(() => {
    if (open) menuItems(menuRef.current)[0]?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    function closeOnOutsidePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer)
  }, [open])

  if (!user) return null

  function close(returnFocus: boolean) {
    setOpen(false)
    if (returnFocus) buttonRef.current?.focus()
  }

  function onMenuKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const items = menuItems(menuRef.current)
    const index = items.indexOf(document.activeElement as HTMLElement)
    const move: Record<string, number | undefined> = {
      ArrowDown: (index + 1) % items.length,
      ArrowUp: (index - 1 + items.length) % items.length,
      Home: 0,
      End: items.length - 1,
    }
    if (event.key in move) {
      event.preventDefault()
      items[move[event.key] as number]?.focus()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      close(true)
    } else if (event.key === 'Tab') {
      close(false)
    }
  }

  function onButtonKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
    }
  }

  async function handleLogout() {
    close(false)
    await logout()
    navigate('/login', { replace: true })
  }

  function chooseLanguage(lang: 'en' | 'tl') {
    setLang(lang)
    close(true)
  }

  const email = user.email
  return (
    <div className="account-menu" ref={rootRef}>
      {open && (
        <div className="account-menu-popover">
          <p className="account-menu-email">{email}</p>
          <div role="menu" id={menuId} aria-labelledby={buttonId} ref={menuRef} onKeyDown={onMenuKeyDown}>
            <Link role="menuitem" tabIndex={-1} to="/settings" onClick={() => close(false)}>
              <svg className="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.4.9a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.4-.9a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2Z" /></svg>
              <span>{t('nav.settings')}</span>
            </Link>
            <div role="group" aria-label={t('language.label')} className="account-menu-group">
              <span className="account-menu-group-label" aria-hidden="true">{t('language.label')}</span>
              {(['en', 'tl'] as const).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  role="menuitemradio"
                  tabIndex={-1}
                  aria-checked={language === lang}
                  onClick={() => chooseLanguage(lang)}
                >
                  <span className="menu-check" aria-hidden="true">{language === lang ? '✓' : ''}</span>
                  <span>{lang === 'en' ? 'English' : 'Filipino'}</span>
                </button>
              ))}
            </div>
            <Link role="menuitem" tabIndex={-1} to="/help" onClick={() => close(false)}>
              <svg className="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 3.4 2.3c-.9.4-1.4 1-1.4 2.2M12 17h.01" /></svg>
              <span>{t('nav.get_help')}</span>
            </Link>
            <div role="separator" className="account-menu-separator" />
            <button type="button" role="menuitem" tabIndex={-1} onClick={() => void handleLogout()}>
              <svg className="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" /></svg>
              <span>{t('nav.log_out')}</span>
            </button>
          </div>
        </div>
      )}
      <Tooltip label={email} enabled={compact}>
        <button
          ref={buttonRef}
          id={buttonId}
          type="button"
          className="account-button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          aria-label={t('nav.account_button', { email })}
          onClick={() => setOpen((value) => !value)}
          onKeyDown={onButtonKeyDown}
        >
          <span className="account-avatar" aria-hidden="true">{initialsFor(email)}</span>
          <span className="account-email" aria-hidden="true">{email}</span>
        </button>
      </Tooltip>
    </div>
  )
}
