import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { useAuth } from './auth/useAuth'
import { LoginPage } from './pages/LoginPage'

// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function DashboardPlaceholder() {
  const { user } = useAuth()
  return <div className="empty-state">{user?.email}</div>
}

// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function RootLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: '/login',
        element: <LoginPage />,
      },
      {
        element: <RequireAuth />,
        children: [
          {
            path: '/dashboard',
            element: <DashboardPlaceholder />,
          },
        ],
      },
      {
        path: '*',
        element: <Navigate to="/login" replace />,
      },
    ],
  },
])
