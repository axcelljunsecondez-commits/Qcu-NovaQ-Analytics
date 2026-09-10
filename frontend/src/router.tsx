import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { RequireRole } from './auth/RequireRole'
import { AppLayout } from './components/layout/AppLayout'
import { AnalysisWorkspace } from './components/analysis/AnalysisWorkspace'
import { ApiState } from './components/ui/ApiState'

// oxlint-disable react/only-export-components -- router module intentionally owns lazy route components and router config
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })))
const GuidedSetupPage = lazy(() => import('./pages/GuidedSetupPage').then((m) => ({ default: m.GuidedSetupPage })))
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
const AnalysesPage = lazy(() => import('./pages/AnalysesPage').then((m) => ({ default: m.AnalysesPage })))
const NewAnalysisPage = lazy(() => import('./pages/NewAnalysisPage').then((m) => ({ default: m.NewAnalysisPage })))
const AnalysisSetupPage = lazy(() => import('./pages/AnalysisSetupPage').then((m) => ({ default: m.AnalysisSetupPage })))
const AnalysisCurrentPage = lazy(() => import('./pages/AnalysisCurrentPage').then((m) => ({ default: m.AnalysisCurrentPage })))
const DecisionEndpointPage = lazy(() => import('./components/analysis/DecisionEndpointPage').then((m) => ({ default: m.DecisionEndpointPage })))

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
        { path: '/register', element: <RegisterPage /> },
        { path: '/verify-email', element: <VerifyEmailPage /> },
        { path: '/forgot-password', element: <ForgotPasswordPage /> },
        { path: '/reset-password', element: <ResetPasswordPage /> },
        {
          path: '/onboarding',
          element: <OnboardingPage />,
        },
        {
          element: <RequireAuth />,
          children: [
            {
              element: <AppLayout />,
              children: [
                {
                  path: '/analyses',
                  element: <AnalysesPage />,
                },
                {
                  path: '/analyses/new',
                  element: <NewAnalysisPage />,
                },
                {
                  path: '/analyses/:analysisId',
                  element: <AnalysisWorkspace />,
                  children: [
                    { index: true, element: <Navigate to="setup" replace /> },
                    { path: 'setup', element: <AnalysisSetupPage /> },
                    { path: 'guided-setup', element: <GuidedSetupPage /> },
                    { path: 'current', element: <AnalysisCurrentPage /> },
                    { path: 'optimize', element: <OptimizePage /> },
                    { path: 'simulate', element: <SimulationPage /> },
                    { path: 'compare', element: <ComparisonPage /> },
                    { path: 'reports', element: <ReportsPage /> },
                    { path: 'decision', element: <DecisionEndpointPage /> },
                  ],
                },
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
