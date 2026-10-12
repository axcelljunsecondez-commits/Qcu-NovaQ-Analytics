import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { RequireRole } from './auth/RequireRole'
import { useAuth } from './auth/useAuth'
import { AppLayout } from './components/layout/AppLayout'
import { AnalysisWorkspace } from './components/analysis/AnalysisWorkspace'
import { ApiState } from './components/ui/ApiState'

// oxlint-disable react/only-export-components -- router module intentionally owns lazy route components and router config
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })))
const HomePage = lazy(() => import('./pages/HomePage').then((m) => ({ default: m.HomePage })))
const GuidedSetupPage = lazy(() => import('./pages/GuidedSetupPage').then((m) => ({ default: m.GuidedSetupPage })))
const AnalysisPage = lazy(() =>
  import('./pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })),
)
const OptimizePage = lazy(() =>
  import('./pages/OptimizePage').then((m) => ({ default: m.OptimizePage })),
)
const SimulationPage = lazy(() =>
  import('./pages/SimulationPage').then((m) => ({ default: m.SimulationPage })),
)
const ResultsPage = lazy(() => import('./pages/ResultsPage').then((m) => ({ default: m.ResultsPage })))
const ReportsPage = lazy(() =>
  import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })),
)
const HelpPage = lazy(() => import('./pages/HelpPage').then((m) => ({ default: m.HelpPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const AnalysesPage = lazy(() => import('./pages/AnalysesPage').then((m) => ({ default: m.AnalysesPage })))
const NewAnalysisPage = lazy(() => import('./pages/NewAnalysisPage').then((m) => ({ default: m.NewAnalysisPage })))
const AnalysisSetupPage = lazy(() => import('./pages/AnalysisSetupPage').then((m) => ({ default: m.AnalysisSetupPage })))
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

// Unknown paths: signed-in users go to My analyses, everyone else to the public Home page.
// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function UnknownRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <ApiState.Loading />
  return <Navigate to={user ? '/analyses' : '/'} replace />
}

// Redirects within the app and keeps the query and hash (deep links survive renames).
// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function KeepQueryRedirect({ to }: { to: string }) {
  const location = useLocation()
  return <Navigate to={`${to}${location.search}${location.hash}`} replace />
}

// The workspace Current and Compare pages became Analysis results (spec §5): /results?analysis=:id.
// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function ResultsRedirect() {
  const { analysisId } = useParams()
  return <Navigate to={`/results?analysis=${analysisId ?? ''}`} replace />
}

export function createAppRouter() {
  return createBrowserRouter([
    {
      element: <RootLayout />,
      children: [
        { path: '/', element: <HomePage /> },
        {
          path: '/login',
          element: <LoginPage />,
        },
        { path: '/register', element: <RegisterPage /> },
        { path: '/verify-email', element: <VerifyEmailPage /> },
        { path: '/forgot-password', element: <ForgotPasswordPage /> },
        { path: '/reset-password', element: <ResetPasswordPage /> },
        {
          element: <RequireAuth />,
          children: [
            // No mandatory onboarding (spec §12, D2); preferences live in Settings.
            { path: '/onboarding', element: <Navigate to="/settings/preferences" replace /> },
            {
              element: <AppLayout />,
              children: [
                { path: '/analyses', element: <AnalysesPage /> },
                { path: '/analyses/new', element: <NewAnalysisPage /> },
                {
                  path: '/analyses/:analysisId',
                  element: <AnalysisWorkspace />,
                  children: [
                    { index: true, element: <Navigate to="data" replace /> },
                    { path: 'data', element: <AnalysisSetupPage /> },
                    // Compatibility: the Setup page is now Data and setup (spec §5).
                    { path: 'setup', element: <KeepQueryRedirect to="../data" /> },
                    { path: 'guided-setup', element: <GuidedSetupPage /> },
                    // Compatibility: Current and Compare are now Analysis results (spec §5, D21).
                    { path: 'current', element: <ResultsRedirect /> },
                    { path: 'plans', element: <OptimizePage /> },
                    // Compatibility: Optimize is now Suggested plans (spec §5).
                    { path: 'optimize', element: <KeepQueryRedirect to="../plans" /> },
                    { path: 'compare', element: <ResultsRedirect /> },
                    { path: 'simulate', element: <SimulationPage /> },
                    { path: 'decision', element: <DecisionEndpointPage /> },
                    { path: 'reports', element: <ReportsPage /> },
                  ],
                },
                { path: '/results', element: <ResultsPage /> },
                { path: '/tools/calculator', element: <AnalysisPage /> },
                { path: '/help', element: <HelpPage /> },
                { path: '/settings', element: <Navigate to="/settings/account" replace /> },
                { path: '/settings/:section', element: <SettingsPage /> },
                {
                  path: '/settings/users',
                  element: <RequireRole role="admin" />,
                  children: [{ index: true, element: <SettingsPage section="users" /> }],
                },
                // Compatibility redirects (spec §5). /settings/users keeps the admin-only check.
                { path: '/dashboard', element: <Navigate to="/analyses" replace /> },
                { path: '/datasets', element: <Navigate to="/settings/files" replace /> },
                { path: '/analysis', element: <Navigate to="/tools/calculator" replace /> },
                { path: '/account', element: <Navigate to="/settings/account" replace /> },
                { path: '/admin', element: <Navigate to="/settings/users" replace /> },
              ],
            },
          ],
        },
        {
          path: '*',
          element: <UnknownRoute />,
        },
      ],
    },
  ])
}

export const router = createAppRouter()
