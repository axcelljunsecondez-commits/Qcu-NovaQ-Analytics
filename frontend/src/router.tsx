import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { RequireRole } from './auth/RequireRole'
import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { DatasetsPage } from './pages/DatasetsPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { OptimizePage } from './pages/OptimizePage'
import { SimulationPage } from './pages/SimulationPage'
import { ComparisonPage } from './pages/ComparisonPage'
import { ReportsPage } from './pages/ReportsPage'
import { AccountPage } from './pages/AccountPage'
import { AdminPage } from './pages/AdminPage'

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
