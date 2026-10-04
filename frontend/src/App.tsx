import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Layout from './components/layout/Layout'
import LoginPage from './components/auth/LoginPage'
import { Spinner } from './components/ui'

const DashboardPage = lazy(() => import('./components/dashboard/DashboardPage'))
const CommunitiesPage = lazy(() => import('./components/communities/CommunitiesPage'))
const HouseholdsPage = lazy(() => import('./components/households/HouseholdsPage'))
const HouseholdDetailPage = lazy(() => import('./components/households/HouseholdDetailPage'))
const BillingPage = lazy(() => import('./components/billing/BillingPage'))
const ExpensesPage = lazy(() => import('./components/expenses/ExpensesPage'))
const MaintenancePage = lazy(() => import('./components/maintenance/MaintenancePage'))
const AnalyticsPage = lazy(() => import('./components/reports/AnalyticsPage'))
const UsersPage = lazy(() => import('./components/users/UsersPage'))
const FieldView = lazy(() => import('./components/field/FieldView'))
const PrintBill = lazy(() => import('./components/billing/PrintBill'))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function FieldOrRedirect() {
  const { user, isField } = useAuth()
  if (!user) return <Spinner />
  return isField ? <FieldView /> : <Navigate to="/" replace />
}

function AdminOrRedirect() {
  const { user, isField } = useAuth()
  if (!user) return <Spinner />
  if (isField) return <Navigate to="/field" replace />
  return <Layout />
}

export default function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Field view: operators and readers */}
      <Route
        path="/field"
        element={
          <ProtectedRoute>
            <FieldOrRedirect />
          </ProtectedRoute>
        }
      />
      {/* Administration: system admins and treasurers */}
      <Route
        element={
          <ProtectedRoute>
            <AdminOrRedirect />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/communities" element={<CommunitiesPage />} />
        <Route path="/households" element={<HouseholdsPage />} />
        <Route path="/households/:householdId" element={<HouseholdDetailPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/billing/print" element={<PrintBill />} />
        <Route path="/expenses" element={<ExpensesPage />} />
        <Route path="/maintenance" element={<MaintenancePage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/team" element={<UsersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
