import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Plus, Trash2, Wallet } from 'lucide-react'
import api from '../../services/api'
import {
  Badge,
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  StatCard,
  formatDate,
  formatMoney,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui'

interface Expense {
  id: string
  expense_date: string
  amount: number
  currency: string
  description: string
  category: string
  receipt_number: string | null
  recorded_by: string | null
  community_id: string
  community_name: string | null
}

interface Summary {
  total: number
  currency: string
  by_category: Record<string, number>
  by_currency: Record<string, number>
  count: number
}

interface Community {
  id: string
  name: string
}

const categories = ['maintenance', 'administrative', 'other']

export default function ExpensesPage() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [communities, setCommunities] = useState<Community[]>([])
  const [loading, setLoading] = useState(true)
  const [communityId, setCommunityId] = useState('')
  const [category, setCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    expense_date: new Date().toISOString().slice(0, 10),
    amount: '',
    description: '',
    category: 'maintenance',
    receipt_number: '',
    community_id: '',
  })

  const load = useCallback(async () => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (communityId) params.community_id = communityId
    if (category) params.category = category
    try {
      const [listRes, summaryRes] = await Promise.all([
        api.get('/expenses/', { params: { ...params, limit: 500 } }),
        api.get('/expenses/summary', {
          params: communityId ? { community_id: communityId } : {},
        }),
      ])
      setExpenses(listRes.data)
      setSummary(summaryRes.data)
    } catch {
      setExpenses([])
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [communityId, category])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    api
      .get('/communities/')
      .then((res) => setCommunities(res.data))
      .catch(() => setCommunities([]))
  }, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/expenses/', {
        expense_date: new Date(form.expense_date).toISOString(),
        amount: Number(form.amount),
        description: form.description.trim(),
        category: form.category,
        receipt_number: form.receipt_number.trim() || null,
        community_id: form.community_id,
      })
      setShowForm(false)
      await load()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail || 'Could not save the expense.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: string) {
    await api.delete(`/expenses/${id}`)
    await load()
  }

  return (
    <div>
      <PageHeader
        title="Expenses"
        subtitle="Money the system spends — kept separate from maintenance reports."
        actions={
          <button
            onClick={() => {
              setForm({
                expense_date: new Date().toISOString().slice(0, 10),
                amount: '',
                description: '',
                category: 'maintenance',
                receipt_number: '',
                community_id: communityId || '',
              })
              setError('')
              setShowForm(true)
            }}
            className={primaryButtonClass}
          >
            <Plus className="h-4 w-4" />
            Record expense
          </button>
        }
      />

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
          <StatCard
            label="Total spent"
            value={
              Object.entries(summary.by_currency)
                .map(([code, value]) => `${code} ${value.toFixed(2)}`)
                .join(' · ') || '0'
            }
            hint={`${summary.count} expense(s)`}
          />
          {categories.map((cat) => (
            <StatCard
              key={cat}
              label={cat}
              value={(summary.by_category[cat] || 0).toFixed(2)}
            />
          ))}
        </div>
      )}

      <Card className="p-4 mb-6">
        <div className="grid gap-3 sm:grid-cols-2 max-w-xl">
          <select
            value={communityId}
            onChange={(e) => setCommunityId(e.target.value)}
            className={inputClass}
          >
            <option value="">All communities</option>
            {communities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={inputClass}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c} className="capitalize">
                {c}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {loading ? (
        <Spinner />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr className="text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Description</th>
                  <th className="px-6 py-3">Category</th>
                  <th className="px-6 py-3">Community</th>
                  <th className="px-6 py-3">Receipt</th>
                  <th className="px-6 py-3 text-right">Amount</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {expenses.map((exp) => (
                  <tr key={exp.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm">{formatDate(exp.expense_date)}</td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {exp.description}
                      {exp.recorded_by && (
                        <span className="block text-xs text-gray-400">by {exp.recorded_by}</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <Badge value={exp.category} />
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{exp.community_name || '—'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{exp.receipt_number || '—'}</td>
                    <td className="px-6 py-4 text-sm text-right font-medium">
                      {formatMoney(exp.currency, exp.amount)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(exp.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete expense"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {expenses.length === 0 && (
            <EmptyState
              icon={Wallet}
              title="No expenses recorded"
              hint="Record what the water system spends: repairs, supplies, electricity."
            />
          )}
        </Card>
      )}

      {showForm && (
        <Modal title="Record expense" onClose={() => setShowForm(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm">
                {error}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Date">
                <input
                  type="date"
                  required
                  value={form.expense_date}
                  onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Amount" hint="Recorded in the community's currency.">
                <input
                  type="number"
                  step="0.01"
                  required
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Community" className="sm:col-span-2">
                <select
                  required
                  value={form.community_id}
                  onChange={(e) => setForm({ ...form, community_id: e.target.value })}
                  className={inputClass}
                >
                  <option value="">— Select community —</option>
                  {communities.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Description" className="sm:col-span-2">
                <input
                  required
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className={inputClass}
                  placeholder="e.g. Replacement valve for the distribution tank"
                />
              </Field>
              <Field label="Category">
                <select
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className={inputClass}
                >
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Receipt no. (optional)">
                <input
                  value={form.receipt_number}
                  onChange={(e) => setForm({ ...form, receipt_number: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className={secondaryButtonClass}
              >
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButtonClass}>
                {saving ? 'Saving...' : 'Save expense'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
