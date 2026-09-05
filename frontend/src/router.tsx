import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { RequireRole } from './auth/RequireRole'
import { AppLayout } from './components/layout/AppLayout'
import { ApiState } from './components/ui/ApiState'

// oxlint-disable react/only-export-components -- router module intentionally owns lazy route components and router config
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const DatasetsPage = lazy(() =>
  import('./pages/DatasetsPage').then((m) => ({ default: m.DatasetsPage })),
)
const AnalysisPage = lazy(() =>
  import('./pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })),
)
const OptimizePage = lazy(() =>
  import('./pages/OptimizePage').then((m) => ({ default: m.OptimizePage })),
)
const SimulationPage = lazy(() =>
  import('./pages/SimulationPage').then((m) => ({ default: m.SimulationPage })),
)
const ComparisonPage = lazy(() =>
  import('./pages/ComparisonPage').then((m) => ({ default: m.ComparisonPage })),
)
const ReportsPage = lazy(() =>
  import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })),
)
const AccountPage = lazy(() =>
  import('./pages/AccountPage').then((m) => ({ default: m.AccountPage })),
)
const AdminPage = lazy(() => import('./pages/AdminPage').then((m) => ({ default: m.AdminPage })))

// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function RootLayout() {
  return (
    <AuthProvider>
      <Suspense fallback={<ApiState.Loading />}>
        <Outlet />
      </Suspense>
    </AuthProvider>
  )
}

export function createAppRouter() {
  return createBrowserRouter([
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
              element: <AppLayout />,
              children: [
                {
                  path: '/dashboard',
                  element: <DashboardPage />,
                },
                {
                  path: '/datasets',
                  element: <DatasetsPage />,
                },
                {
                  path: '/analysis',
                  element: <AnalysisPage />,
                },
                {
                  path: '/optimize',
                  element: <OptimizePage />,
                },
                {
                  path: '/simulate',
                  element: <SimulationPage />,
                },
                {
                  path: '/compare',
                  element: <ComparisonPage />,
                },
                {
                  path: '/reports',
                  element: <ReportsPage />,
                },
                {
                  path: '/account',
                  element: <AccountPage />,
                },
                {
                  path: '/admin',
                  element: <RequireRole role="admin" />,
                  children: [{ index: true, element: <AdminPage /> }],
                },
              ],
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
}

export const router = createAppRouter()
