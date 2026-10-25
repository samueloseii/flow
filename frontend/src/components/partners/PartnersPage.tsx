import { FormEvent, useEffect, useState } from 'react'
import { Handshake, Plus, Trash2 } from 'lucide-react'
import api from '../../services/api'
import { Card, EmptyState, Field, Modal, PageHeader, Spinner, inputClass, primaryButtonClass, secondaryButtonClass } from '../ui'

interface Partner {
  id: string
  name: string
  country: string
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  description: string | null
  communities_count: number
  organization_id: string | null
  organization_name: string | null
}

interface Organization { id: string; name: string; partners_count: number }

const emptyForm = { organization_id: '', new_organization_name: '', name: '', country: '', contact_name: '', contact_email: '', contact_phone: '', description: '' }

export default function PartnersPage() {
  const [partners, setPartners] = useState<Partner[]>([])
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    Promise.all([api.get('/partners/'), api.get('/organizations/')])
      .then(([p, o]) => { setPartners(p.data); setOrganizations(o.data) })
      .catch(() => setPartners([]))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/partners/', {
        organization_id: form.organization_id || null,
        new_organization_name: form.organization_id ? null : form.new_organization_name.trim(),
        name: form.name,
        country: form.country,
        contact_name: form.contact_name || null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
        description: form.description || null,
      })
      setShowForm(false)
      setForm(emptyForm)
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not create the partner.')
    } finally {
      setSaving(false)
    }
  }

  async function remove(p: Partner) {
    if (!window.confirm(`Delete ${p.name}? Its water committees must be removed first.`)) return
    try { await api.delete(`/partners/${p.id}`); load() }
    catch (err: any) { window.alert(err?.response?.data?.detail ?? 'Could not delete this partner.') }
  }

  return (
    <div>
      <PageHeader
        title="Partners"
        subtitle="Organization → Partner. Partners support water committees; each partner's administrators see only their own committees."
        actions={<button onClick={() => { setForm({ ...emptyForm, organization_id: organizations[0]?.id ?? '' }); setError(''); setShowForm(true) }} className={primaryButtonClass}><Plus className="h-4 w-4" />New partner</button>}
      />
      {loading ? <Spinner /> : partners.length === 0 ? (
        <EmptyState icon={Handshake} title="No partners yet" hint="Add a partner, then its water committees." />
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-5 py-3">Organization</th>
                <th className="px-5 py-3">Partner</th>
                <th className="px-5 py-3">Country</th>
                <th className="px-5 py-3">Contact</th>
                <th className="px-5 py-3 text-right">Communities</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {partners.map((p) => (
                <tr key={p.id}>
                  <td className="px-5 py-3 text-gray-700">{p.organization_name ?? '—'}</td>
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-900">{p.name}</p>
                    {p.description && <p className="text-xs text-gray-500">{p.description}</p>}
                  </td>
                  <td className="px-5 py-3 text-gray-700">{p.country}</td>
                  <td className="px-5 py-3 text-gray-700">
                    {p.contact_name ?? '—'}
                    {p.contact_email && <p className="text-xs text-gray-500">{p.contact_email}</p>}
                    {p.contact_phone && <p className="text-xs text-gray-500">{p.contact_phone}</p>}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-700">{p.communities_count}</td>
                  <td className="px-5 py-3 text-right">
                    <button onClick={() => remove(p)} className="text-gray-400 hover:text-red-600" title="Delete"><Trash2 className="h-4 w-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {showForm && (
        <Modal title="New partner" onClose={() => setShowForm(false)}>
          <form onSubmit={submit} className="space-y-4">
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Organization" className="sm:col-span-2" hint="The body this partner belongs to">
                <select className={inputClass} value={form.organization_id} onChange={(e) => setForm({ ...form, organization_id: e.target.value })}>
                  {organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                  <option value="">New organization…</option>
                </select>
              </Field>
              {!form.organization_id && (
                <Field label="New organization name" className="sm:col-span-2">
                  <input className={inputClass} value={form.new_organization_name} onChange={(e) => setForm({ ...form, new_organization_name: e.target.value })} required />
                </Field>
              )}
              <Field label="Partner name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
              <Field label="Country"><input className={inputClass} value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} required /></Field>
              <Field label="Contact name"><input className={inputClass} value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} /></Field>
              <Field label="Contact phone"><input className={inputClass} value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></Field>
              <Field label="Contact email" className="sm:col-span-2"><input type="email" className={inputClass} value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} /></Field>
              <Field label="Notes" className="sm:col-span-2"><input className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className={primaryButtonClass} disabled={saving}>{saving ? 'Saving…' : 'Create partner'}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
