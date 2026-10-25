import { useEffect, useState } from 'react'
import { ArrowRight, Check } from 'lucide-react'
import api from '../../services/api'
import { Card, PageHeader, Spinner, StatCard, formatMoney } from '../ui'

interface SystemDashboard {
  total_partners: number
  total_communities: number
  total_households: number
  total_users: number
  overall_collection_rate: number
  total_revenue: number
  total_arrears: number
}

interface Community {
  id: string
  name: string
  currency: string
}

const quickActions = [
  { href: '/households', label: 'Register a household' },
  { href: '/billing', label: 'Generate bills' },
  { href: '/expenses', label: 'Record an expense' },
  { href: '/maintenance', label: 'Review issue reports' },
]

export default function DashboardPage() {
  const [data, setData] = useState<SystemDashboard | null>(null)
  const [communities, setCommunities] = useState<Community[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.get('/dashboard/system'), api.get('/communities/')])
      .then(([dashboardRes, communitiesRes]) => {
        setData(dashboardRes.data)
        setCommunities(communitiesRes.data)
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const currency = communities[0]?.currency ?? ''
  const setupSteps = [
    { label: 'Create your first community and its tariff', href: '/communities', done: (data?.total_communities ?? 0) > 0 },
    { label: 'Add operators and a treasurer', href: '/team', done: (data?.total_users ?? 0) > 1 },
    { label: 'Register households and their meters', href: '/households', done: (data?.total_households ?? 0) > 0 },
  ]
  const setupComplete = setupSteps.every((s) => s.done)

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Current state of the water systems you manage" />

      {!setupComplete && (
        <Card className="p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-900">Get set up</h2>
          <p className="text-xs text-gray-500 mt-0.5">Three steps before readings and billing can start.</p>
          <ol className="mt-4 space-y-2">
            {setupSteps.map((step) => (
              <li key={step.href}>
                <a
                  href={step.href}
                  className={`flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm transition-colors ${
                    step.done
                      ? 'border-gray-100 bg-gray-50 text-gray-500'
                      : 'border-gray-200 text-gray-800 hover:border-primary-300 hover:bg-primary-50'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    {step.done && <Check className="h-4 w-4 text-emerald-600" />}
                    {step.label}
                  </span>
                  {!step.done && <ArrowRight className="h-4 w-4 text-gray-400" />}
                </a>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Communities" value={data.total_communities} />
          <StatCard label="Households" value={data.total_households} />
          <StatCard
            label="Collection rate"
            value={`${data.overall_collection_rate}%`}
            tone={data.overall_collection_rate >= 80 ? 'positive' : 'warning'}
          />
          <StatCard label="Collected" value={formatMoney(currency, data.total_revenue)} />
          <StatCard
            label="Outstanding"
            value={formatMoney(currency, data.total_arrears)}
            tone={data.total_arrears > 0 ? 'danger' : 'default'}
          />
          <StatCard label="Partners" value={data.total_partners} />
          <StatCard label="Accounts" value={data.total_users} />
        </div>
      )}

      <Card className="mt-6 p-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-3">Common tasks</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {quickActions.map((action) => (
            <a
              key={action.href}
              href={action.href}
              className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-4 py-3 text-sm text-gray-700 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              {action.label}
              <ArrowRight className="h-4 w-4 text-gray-400" />
            </a>
          ))}
        </div>
      </Card>
    </div>
  )
}
