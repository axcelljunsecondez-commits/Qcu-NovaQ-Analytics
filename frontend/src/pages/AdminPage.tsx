import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listUsers, createUser, updateUser } from '../api/users'
import { ApiState } from '../components/ui/ApiState'
import type { Role } from '../api/types'

function detailMessages(error: unknown): string[] {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const msg = (item as { msg?: string }).msg
      return msg ?? String(item)
    })
  }
  return detail ? [String(detail)] : []
}

export function AdminPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('analyst')
  const [banner, setBanner] = useState<string | null>(null)
  const [inlineErrors, setInlineErrors] = useState<string[]>([])

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: listUsers,
  })

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setEmail('')
      setPassword('')
      setRole('analyst')
      setBanner(null)
      setInlineErrors([])
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: unknown) => {
      const messages = detailMessages(error)
      if ((error as { response?: { status?: number } }).response?.status === 409) {
        setBanner(t('admin.duplicate'))
        setInlineErrors([])
      } else if (messages.length > 0) {
        setBanner(null)
        setInlineErrors(messages)
      } else {
        setBanner(null)
        setInlineErrors([t('errors.server')])
      }
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => updateUser(id, { active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  function handleCreate(event: FormEvent) {
    event.preventDefault()
    createMutation.mutate({ email, password, role })
  }

  function handleToggle(id: number, current: boolean) {
    if (window.confirm(t('admin.confirm_deactivate'))) {
      toggleMutation.mutate({ id, active: !current })
    }
  }

  const users = usersQuery.data?.users ?? []

  return (
    <div>
      <h1 className="page-title">{t('admin.title')}</h1>

      <div className="card">
        <h2 className="card-title">{t('admin.create')}</h2>
        <form className="form-row" onSubmit={handleCreate}>
          <div className="form-field">
            <label htmlFor="admin-email">{t('login.email')}</label>
            <input
              id="admin-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="admin-password">{t('login.password')}</label>
            <input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="admin-role">{t('admin.role')}</label>
            <select id="admin-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="analyst">analyst</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <button type="submit" disabled={createMutation.isPending}>
            {t('admin.create')}
          </button>
        </form>
        {banner && <div className="alert alert-error">{banner}</div>}
        {inlineErrors.length > 0 && (
          <div className="alert alert-error">
            {inlineErrors.map((message) => (
              <div key={message}>{message}</div>
            ))}
          </div>
        )}
      </div>

      {usersQuery.isLoading && <ApiState.Loading />}
      {usersQuery.isError && <ApiState.ErrorState error={usersQuery.error} />}

      {usersQuery.isSuccess &&
        (users.length === 0 ? (
          <ApiState.Empty message={t('admin.no_users')} />
        ) : (
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th>{t('account.email')}</th>
                  <th>{t('admin.role')}</th>
                  <th>{t('admin.active')}</th>
                  <th>{t('account.created')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                    <td>
                      <span className={`badge ${u.active ? 'badge-ok' : 'badge-bad'}`}>
                        {u.active ? '✓' : '✗'}
                      </span>
                    </td>
                    <td>{new Date(u.created_at).toLocaleDateString()}</td>
                    <td>
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => handleToggle(u.id, u.active)}
                        disabled={toggleMutation.isPending}
                      >
                        {u.active ? t('admin.deactivate') : t('admin.activate')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}
