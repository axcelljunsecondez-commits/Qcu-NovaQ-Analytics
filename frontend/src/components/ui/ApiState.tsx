import { useTranslation } from 'react-i18next'

export function Loading() {
  const { t } = useTranslation()
  return (
    <div className="empty-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{t('common.loading')}</p>
    </div>
  )
}

export function Empty({ message }: { message: string }) {
  return <div className="empty-state" role="status">{message}</div>
}

export function ErrorState({ error }: { error?: unknown }) {
  const { t } = useTranslation()
  const message =
    (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail ??
    t('errors.server')
  return <div className="alert alert-error" role="alert">{String(message)}</div>
}

export function Forbidden() {
  const { t } = useTranslation()
  return (
    <div className="card error-state" role="alert">
      <h2>{t('errors.forbidden')}</h2>
    </div>
  )
}

// oxlint-disable-next-line react/only-export-components -- convenience aggregate of state components
export const ApiState = {
  Loading,
  Empty,
  ErrorState,
  Forbidden,
}
