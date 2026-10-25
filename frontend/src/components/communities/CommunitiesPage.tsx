import { FormEvent, useEffect, useState } from 'react'
import { MapPin, Plus, Trash2 } from 'lucide-react'
import api from '../../services/api'
import {
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui'

interface Community {
  id: string
  name: string
  country: string
  region: string | null
  total_connections: number
  water_system_type: string
  currency: string
  tariff_fixed: number
  tariff_per_m3: number
  water_committee_id: string | null
  water_committee_name: string | null
}

interface Committee {
  id: string
  name: string
}

const systemTypeLabel: Record<string, string> = {
  gravity_fed: 'Gravity-fed',
  pumped: 'Pumped',
  mixed: 'Mixed',
}

const emptyForm = {
  name: '',
  country: '',
  region: '',
  currency: 'USD',
  water_system_type: 'gravity_fed',
  community_size: 'small',
  population: '',
  tariff_fixed: '',
  tariff_per_m3: '',
  partner_id: '',
  new_partner_name: '',
  water_committee_id: '',
}

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<Community[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    api.get('/water-committees/').then((r) => setCommittees(r.data)).catch(() => setCommittees([]))
    api.get('/communities/')
      .then((r) => setCommunities(r.data))
      .catch(() => setCommunities([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function openForm() {
    setForm({ ...emptyForm, water_committee_id: committees[0]?.id ?? '' })
    setError('')
    setShowForm(true)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/communities/', {
        name: form.name,
        country: form.country,
        region: form.region || null,
        currency: form.currency,
        water_system_type: form.water_system_type,
        community_size: form.community_size,
        population: form.population ? Number(form.population) : null,
        tariff_fixed: Number(form.tariff_fixed || 0),
        tariff_per_m3: Number(form.tariff_per_m3 || 0),
        water_committee_id: form.water_committee_id,
      })
      setShowForm(false)
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the community.')
    } finally {
      setSaving(false)
    }
  }

  async function remove(community: { id: string; name: string }) {
    if (!window.confirm(`Delete ${community.name}?`)) return
    try {
      await api.delete(`/communities/${community.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not delete this community.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Communities"
        subtitle="Water systems, their tariffs and the organization responsible"
        actions={
          <button onClick={openForm} className={primaryButtonClass}>
            <Plus className="h-4 w-4" />
            New community
          </button>
        }
      />

      {loading ? (
        <Spinner />
      ) : communities.length === 0 ? (
        <Card>
          <EmptyState
            icon={MapPin}
            title="No communities yet"
            hint="Add the first community with its tariff, then register households against it."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {communities.map((c) => (
            <Card key={c.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{c.name}</h3>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {c.region ? `${c.region}, ` : ''}
                    {c.country}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {systemTypeLabel[c.water_system_type] ?? c.water_system_type}
                  </span>
                  <button
                    aria-label={`Delete ${c.name}`}
                    className="text-gray-300 hover:text-red-600"
                    onClick={() => remove(c)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <dl className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-gray-500 text-xs">Connections</dt>
                  <dd className="font-medium text-gray-900">{c.total_connections}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Water committee</dt>
                  <dd className="font-medium text-gray-900">{c.water_committee_name ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Tariff</dt>
                  <dd className="font-medium text-gray-900">
                    {c.currency} {c.tariff_fixed} + {c.tariff_per_m3}/m³
                  </dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      )}

      {showForm && (
        <Modal
          title="New community"
          description="Tariffs are used when bills are generated."
          onClose={() => setShowForm(false)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">
                {error}
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Community name">
                <input
                  className={inputClass}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </Field>
              <Field label="Country">
                <input
                  className={inputClass}
                  value={form.country}
                  onChange={(e) => setForm({ ...form, country: e.target.value })}
                  required
                />
              </Field>
              <Field label="Region">
                <input
                  className={inputClass}
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                />
              </Field>
              <Field label="Population">
                <input
                  type="number"
                  min="0"
                  className={inputClass}
                  value={form.population}
                  onChange={(e) => setForm({ ...form, population: e.target.value })}
                />
              </Field>
              <Field label="Water system">
                <select
                  className={inputClass}
                  value={form.water_system_type}
                  onChange={(e) => setForm({ ...form, water_system_type: e.target.value })}
                >
                  <option value="gravity_fed">Gravity-fed</option>
                  <option value="pumped">Pumped</option>
                  <option value="mixed">Mixed</option>
                </select>
              </Field>
              <Field label="Size">
                <select
                  className={inputClass}
                  value={form.community_size}
                  onChange={(e) => setForm({ ...form, community_size: e.target.value })}
                >
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                </select>
              </Field>
              <Field label="Currency" hint="Three-letter code, e.g. GHS, USD">
                <input
                  className={inputClass}
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                  maxLength={5}
                  required
                />
              </Field>
              <Field label="Fixed charge per bill">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  className={inputClass}
                  value={form.tariff_fixed}
                  onChange={(e) => setForm({ ...form, tariff_fixed: e.target.value })}
                  required
                />
              </Field>
              <Field label="Charge per m³">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  className={inputClass}
                  value={form.tariff_per_m3}
                  onChange={(e) => setForm({ ...form, tariff_per_m3: e.target.value })}
                  required
                />
              </Field>
              <Field label="Water committee" className="sm:col-span-2" hint="The committee that runs this water system">
                <select
                  className={inputClass}
                  value={form.water_committee_id}
                  onChange={(e) => setForm({ ...form, water_committee_id: e.target.value })}
                  required
                >
                  <option value="">Choose a water committee</option>
                  {committees.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className={secondaryButtonClass}
                onClick={() => setShowForm(false)}
              >
                Cancel
              </button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>
                {saving ? 'Saving…' : 'Create community'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
