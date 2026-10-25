import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Home, Plus, Search, Trash2 } from 'lucide-react'
import api from '../../services/api'
import { useAuth } from '../../contexts/AuthContext'
import {
  Badge,
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  formatDate,
  formatMoney,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui'

export interface Household {
  id: string
  account_number: string
  head_of_household: string
  address: string | null
  phone: string | null
  members_count: number
  status: string
  has_meter: boolean
  outstanding_balance: number
  community_id: string
  meter_serial_number: string | null
  last_reading_value: number | null
  last_reading_date: string | null
  community_name: string | null
  currency: string | null
}

interface Community {
  id: string
  name: string
}

const emptyForm = {
  account_number: '',
  head_of_household: '',
  address: '',
  phone: '',
  members_count: '1',
  community_id: '',
  meter_serial_number: '',
  meter_brand: '',
  meter_initial_reading: '0',
}

export default function HouseholdsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [households, setHouseholds] = useState<Household[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const res = await api.get('/households/', { params: { limit: 500 } })
      setHouseholds(res.data)
    } catch {
      setHouseholds([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    api
      .get('/communities/')
      .then((res) => setCommunities(res.data))
      .catch(() => setCommunities([]))
  }, [])

  async function handleDelete(household: Household) {
    if (
      !window.confirm(
        `Delete ${household.head_of_household} (${household.account_number}) and all its readings, bills and payments?`
      )
    )
      return
    try {
      await api.delete(`/households/${household.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not delete this account.')
    }
  }

  function openForm() {
    setForm({ ...emptyForm, community_id: user?.community_id || '' })
    setError('')
    setShowForm(true)
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/households/', {
        account_number: form.account_number.trim(),
        head_of_household: form.head_of_household.trim(),
        address: form.address.trim() || null,
        phone: form.phone.trim() || null,
        members_count: Number(form.members_count) || 1,
        community_id: form.community_id,
        meter_serial_number: form.meter_serial_number.trim() || null,
        meter_brand: form.meter_brand.trim() || null,
        meter_initial_reading: Number(form.meter_initial_reading) || 0,
      })
      setShowForm(false)
      await load()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail || 'Could not register the household. Check the details and try again.')
    } finally {
      setSaving(false)
    }
  }

  const term = search.trim().toLowerCase()
  const filtered = term
    ? households.filter(
        (h) =>
          h.head_of_household.toLowerCase().includes(term) ||
          h.account_number.toLowerCase().includes(term) ||
          (h.meter_serial_number || '').toLowerCase().includes(term),
      )
    : households

  return (
    <div>
      <PageHeader
        title="Households"
        subtitle="Water accounts, one per household. Administrators and operators can register them; readings follow the active meter."
        actions={
          <button onClick={openForm} className={primaryButtonClass}>
            <Plus className="h-4 w-4" />
            Register household
          </button>
        }
      />

      <div className="mb-6 relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name, account or meter number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={`${inputClass} pl-10`}
        />
      </div>

      {loading ? (
        <Spinner />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr className="text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-6 py-3">Account</th>
                  <th className="px-6 py-3">Head of household</th>
                  <th className="px-6 py-3">Community</th>
                  <th className="px-6 py-3">Meter</th>
                  <th className="px-6 py-3">Last reading</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Balance</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((h) => (
                  <tr
                    key={h.id}
                    onClick={() => navigate(`/households/${h.id}`)}
                    className="cursor-pointer hover:bg-primary-50/50 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-medium text-primary-600">
                      {h.account_number}
                    </td>
                    <td className="px-6 py-4 text-sm">{h.head_of_household}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{h.community_name || '—'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {h.meter_serial_number || (h.has_meter ? 'Yes' : 'No meter')}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {h.last_reading_value != null ? (
                        <>
                          <span className="font-mono">{h.last_reading_value.toFixed(1)} m³</span>
                          <span className="block text-xs text-gray-400">
                            {formatDate(h.last_reading_date)}
                          </span>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <Badge value={h.status} />
                    </td>
                    <td className="px-6 py-4 text-sm text-right font-medium">
                      <span
                        className={h.outstanding_balance > 0 ? 'text-red-600' : 'text-emerald-600'}
                      >
                        {formatMoney(h.currency, h.outstanding_balance)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          aria-label={`Delete ${h.account_number}`}
                          className="text-gray-300 hover:text-red-600"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(h)
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                        <ChevronRight className="h-4 w-4 text-gray-300" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <EmptyState
              icon={Home}
              title="No households found"
              hint="Register a household to start recording readings and bills."
            />
          )}
        </Card>
      )}

      {showForm && (
        <Modal
          title="Register household"
          description="Creates the water account and, optionally, its meter."
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleCreate} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm">
                {error}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Account number">
                <input
                  required
                  value={form.account_number}
                  onChange={(e) => setForm({ ...form, account_number: e.target.value })}
                  className={inputClass}
                  placeholder="C01-0042"
                />
              </Field>
              <Field label="Head of household">
                <input
                  required
                  value={form.head_of_household}
                  onChange={(e) => setForm({ ...form, head_of_household: e.target.value })}
                  className={inputClass}
                  placeholder="María López"
                />
              </Field>
              <Field label="Community">
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
              <Field label="Members">
                <input
                  type="number"
                  min="1"
                  value={form.members_count}
                  onChange={(e) => setForm({ ...form, members_count: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Address (optional)">
                <input
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Phone (optional)">
                <input
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>

            <div className="pt-2 border-t border-gray-100">
              <p className="text-sm font-medium text-gray-700 mb-3">Meter (optional)</p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Serial number">
                  <input
                    value={form.meter_serial_number}
                    onChange={(e) => setForm({ ...form, meter_serial_number: e.target.value })}
                    className={inputClass}
                    placeholder="M-C01-0042"
                  />
                </Field>
                <Field label="Brand">
                  <input
                    value={form.meter_brand}
                    onChange={(e) => setForm({ ...form, meter_brand: e.target.value })}
                    className={inputClass}
                  />
                </Field>
                <Field label="Current reading" hint="Cumulative value shown on the dial today.">
                  <input
                    type="number"
                    step="0.1"
                    value={form.meter_initial_reading}
                    onChange={(e) => setForm({ ...form, meter_initial_reading: e.target.value })}
                    className={inputClass}
                  />
                </Field>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className={secondaryButtonClass}
              >
                Cancel
              </button>
              <button type="submit" disabled={saving} className={primaryButtonClass}>
                {saving ? 'Saving...' : 'Register household'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
