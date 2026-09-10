import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { verifyEmail } from '../api/auth'
import { takeFragmentToken } from '../auth/fragmentToken'

export function VerifyEmailPage() {
  const { t } = useTranslation()
  const [state, setState] = useState<'working' | 'success' | 'invalid'>('working')
  useEffect(() => {
    const token = takeFragmentToken()
    if (!token) {
      setState('invalid')
      return
    }
    void verifyEmail(token).then(() => setState('success')).catch(() => setState('invalid'))
  }, [])
  return <div className="login-page"><div className="card login-card">
    <h1 className="login-title">{t('auth.verify_title')}</h1>
    <div className={`alert ${state === 'success' ? 'alert-ok' : state === 'invalid' ? 'alert-error' : ''}`}>
      {t(`auth.verify_${state}`)}
    </div>
    <Link to="/login">{t('auth.back_login')}</Link>
    {state === 'invalid' && <Link to="/register?mode=resend">{t('auth.resend')}</Link>}
  </div></div>
}
