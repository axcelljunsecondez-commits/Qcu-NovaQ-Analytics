import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { DatasetsPage } from './pages/DatasetsPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { OptimizePage } from './pages/OptimizePage'
import { SimulationPage } from './pages/SimulationPage'
import { ComparisonPage } from './pages/ComparisonPage'

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
