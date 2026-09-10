import { Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'
import { Forbidden } from '../components/ui/ApiState'

export function RequireRole({ role }: { role: 'admin' }) {
  const { user } = useAuth()

  if (user?.role !== role) {
    return <Forbidden />
  }

  return <Outlet />
}
