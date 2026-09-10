import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { authConfig, googleNonce } from '../api/auth'
import { useAuth } from './useAuth'
import { apiErrorCode } from './fragmentToken'

type GoogleCredentialResponse = { credential?: string }
type GoogleAccounts = {
  id: {
    initialize: (options: Record<string, unknown>) => void
    renderButton: (element: HTMLElement, options: Record<string, unknown>) => void
    disableAutoSelect: () => void
  }
}

declare global {
  interface Window {
    google?: { accounts: GoogleAccounts }
  }
}

let googleScript: Promise<void> | null = null

function loadGoogleScript(): Promise<void> {
  if (window.google) return Promise.resolve()
  if (googleScript) return googleScript
  googleScript = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Google Identity Services script failed'))
    document.head.appendChild(script)
  })
  return googleScript
}

export function GoogleSignInButton({
  onSuccess,
  onCredential,
}: {
  onSuccess?: () => void
  onCredential?: (credential: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const { loginWithGoogle } = useAuth()
  const container = useRef<HTMLDivElement>(null)
  const submitting = useRef(false)
  const successRef = useRef(onSuccess)
  const credentialRef = useRef(onCredential)
  const loginRef = useRef(loginWithGoogle)
  successRef.current = onSuccess
  credentialRef.current = onCredential
  loginRef.current = loginWithGoogle
  const [error, setError] = useState<string | null>(null)
  const config = useQuery({ queryKey: ['auth-config'], queryFn: authConfig, retry: false })

  useEffect(() => {
    let cancelled = false
    if (!config.data?.google_sign_in_enabled || !config.data.google_client_id) return
    void (async () => {
      try {
        const { nonce } = await googleNonce()
        await loadGoogleScript()
        if (cancelled || !container.current || !window.google) return
        window.google.accounts.id.initialize({
          client_id: config.data.google_client_id,
          nonce,
          callback: async (response: GoogleCredentialResponse) => {
            if (!response.credential || submitting.current) return
            submitting.current = true
            setError(null)
            try {
              if (credentialRef.current) await credentialRef.current(response.credential)
              else await loginRef.current(response.credential)
              successRef.current?.()
            } catch (err) {
              setError(
                apiErrorCode(err) === 'account_link_required'
                  ? t('auth.google_link_required')
                  : t('auth.google_failed'),
              )
            } finally {
              submitting.current = false
            }
          },
        })
        container.current.replaceChildren()
        window.google.accounts.id.renderButton(container.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
        })
      } catch {
        if (!cancelled) setError(t('auth.google_failed'))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [config.data, t])

  if (!config.data?.google_sign_in_enabled) return null
  return (
    <div className="google-sign-in">
      <div ref={container} aria-label={t('auth.continue_google')} />
      {error && <div className="alert alert-error">{error}</div>}
    </div>
  )
}
