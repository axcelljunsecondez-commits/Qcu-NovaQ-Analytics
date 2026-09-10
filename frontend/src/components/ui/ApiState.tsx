import { useTranslation } from 'react-i18next'

export function Loading() {
  const { t } = useTranslation()
  return (
    <div className="empty-state">
      <div className="spinner" />
      <p>{t('common.loading')}</p>
    </div>
  )
}

export function Empty({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>
}

export function ErrorState({ error }: { error?: unknown }) {
  const { t } = useTranslation()
  const message =
    (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail ??
    t('errors.server')
  return <div className="alert alert-error">{String(message)}</div>
}

export function Forbidden() {
  const { t } = useTranslation()
  return (
    <div className="card error-state">
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
