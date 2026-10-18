import { FormEvent, useEffect, useState } from 'react'
import { Building2, Plus, Trash2 } from 'lucide-react'
import api from '../../services/api'
import {
  Card, EmptyState, Field, Modal, PageHeader, Spinner, formatMoney,
  inputClass, primaryButtonClass, secondaryButtonClass,
} from '../ui'

interface Committee {
  id: string
  name: string
  partner_id: string
  partner_name: string | null
  country: string | null
  region: string | null
  contact_name: string | null
  contact_phone: string | null
  community_count: number
  household_count: number
}

interface Financials {
  currency: string
  total_billed: number
  total_collected: number
  outstanding: number
  total_expenses: number
  net_position: number
  communities: {
    community_id: string
    community_name: string
    total_billed: number
    total_collected: number
    outstanding: number
    total_expenses: number
  }[]
}

const emptyForm = { name: '', partner_id: '', new_partner_name: '', country: '', region: '', contact_name: '', contact_phone: '' }

export default function WaterCommitteesPage() {
  const [committees, setCommittees] = useState<Committee[]>([])
  const [partners, setPartners] = useState<{ id: string; name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Committee | null>(null)
  const [financials, setFinancials] = useState<Financials | null>(null)

  function load() {
    setLoading(true)
    Promise.all([api.get('/water-committees/'), api.get('/partners/').catch(() => ({ data: [] }))])
      .then(([c, p]) => { setCommittees(c.data); setPartners(p.data) })
      .catch(() => setCommittees([]))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  useEffect(() => {
    if (!selected) return
    setFinancials(null)
    api.get(`/water-committees/${selected.id}/financials`).then((r) => setFinancials(r.data)).catch(() => setFinancials(null))
  }, [selected])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      let partnerId = form.partner_id
      if (!partnerId && partners.length === 0) {
        const created = await api.post('/partners/', { name: form.new_partner_name.trim() || 'Partner organisation', country: form.country || 'US' })
        partnerId = created.data.id
      }
      await api.post('/water-committees/', {
        name: form.name, partner_id: partnerId || null, country: form.country || null, region: form.region || null,
        contact_name: form.contact_name || null, contact_phone: form.contact_phone || null,
      })
      setShowForm(false); load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the water committee.')
    } finally { setSaving(false) }
  }

  async function remove(c: Committee) {
    if (!window.confirm(`Delete ${c.name}?`)) return
    try { await api.delete(`/water-committees/${c.id}`); if (selected?.id === c.id) setSelected(null); load() }
    catch (err: any) { window.alert(err?.response?.data?.detail ?? 'Could not delete this committee.') }
  }

  return (
    <div>
      <PageHeader
        title="Water committees"
        subtitle="The bodies that run the water systems. Each committee manages its communities, tariffs and money."
        actions={<button onClick={() => { setForm({ ...emptyForm, partner_id: partners[0]?.id ?? '' }); setError(''); setShowForm(true) }} className={primaryButtonClass}><Plus className="h-4 w-4" />New committee</button>}
      />
      {loading ? <Spinner /> : committees.length === 0 ? (
        <EmptyState icon={Building2} title="No water committees yet" hint="Add the committee first, then its communities and households." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1 p-0 overflow-hidden">
            <ul className="divide-y divide-gray-100">
              {committees.map((c) => (
                <li key={c.id} className={`px-5 py-4 cursor-pointer hover:bg-gray-50 ${selected?.id === c.id ? 'bg-primary-50' : ''}`} onClick={() => setSelected(c)}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-gray-900">{c.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{c.partner_name ?? '—'}{c.region ? ` · ${c.region}` : ''}</p>
                      <p className="text-xs text-gray-500 mt-1">{c.community_count} communities · {c.household_count} households</p>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); remove(c) }} className="text-gray-400 hover:text-red-600" title="Delete"><Trash2 className="h-4 w-4" /></button>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <div className="lg:col-span-2">
            {!selected ? (
              <Card><p className="text-sm text-gray-500">Select a committee to see its finances across all its communities.</p></Card>
            ) : !financials ? <Spinner /> : (
              <Card>
                <h3 className="font-semibold text-gray-900 mb-1">{selected.name}</h3>
                <p className="text-xs text-gray-500 mb-4">{selected.contact_name ? `${selected.contact_name}${selected.contact_phone ? ` · ${selected.contact_phone}` : ''}` : 'Consolidated finances'}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {[
                    ['Billed', financials.total_billed], ['Collected', financials.total_collected],
                    ['Outstanding', financials.outstanding], ['Expenses', financials.total_expenses],
                  ].map(([label, value]) => (
                    <div key={label as string} className="rounded-lg border border-gray-100 p-3">
                      <p className="text-xs text-gray-500">{label}</p>
                      <p className="text-lg font-semibold text-gray-900">{formatMoney(financials.currency, value as number)}</p>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-gray-600 mb-4">Net position (collected − expenses): <span className={`font-semibold ${financials.net_position >= 0 ? 'text-green-700' : 'text-red-700'}`}>{formatMoney(financials.currency, financials.net_position)}</span></p>
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-xs text-gray-500 border-b"><th className="py-2">Community</th><th className="py-2 text-right">Billed</th><th className="py-2 text-right">Collected</th><th className="py-2 text-right">Outstanding</th><th className="py-2 text-right">Expenses</th></tr></thead>
                  <tbody>
                    {financials.communities.map((r) => (
                      <tr key={r.community_id} className="border-b border-gray-50">
                        <td className="py-2 text-gray-900">{r.community_name}</td>
                        <td className="py-2 text-right">{formatMoney(financials.currency, r.total_billed)}</td>
                        <td className="py-2 text-right">{formatMoney(financials.currency, r.total_collected)}</td>
                        <td className="py-2 text-right">{formatMoney(financials.currency, r.outstanding)}</td>
                        <td className="py-2 text-right">{formatMoney(financials.currency, r.total_expenses)}</td>
                      </tr>
                    ))}
                    {financials.communities.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-gray-500">No communities under this committee yet.</td></tr>}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        </div>
      )}

      {showForm && (
        <Modal title="New water committee" onClose={() => setShowForm(false)}>
          <form onSubmit={submit} className="space-y-4">
            {error && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{error}</p>}
            <Field label="Committee name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
            {partners.length > 0 ? (
              <Field label="Supporting partner organisation">
                <select className={inputClass} value={form.partner_id} onChange={(e) => setForm({ ...form, partner_id: e.target.value })}>
                  {partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </Field>
            ) : (
              <Field label="Partner organisation" hint="The organisation supporting this committee"><input className={inputClass} value={form.new_partner_name} onChange={(e) => setForm({ ...form, new_partner_name: e.target.value })} /></Field>
            )}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Country"><input className={inputClass} value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} /></Field>
              <Field label="Region"><input className={inputClass} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} /></Field>
              <Field label="Contact person"><input className={inputClass} value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} /></Field>
              <Field label="Contact phone"><input className={inputClass} value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></Field>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
