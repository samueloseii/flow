import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Calculator, Pencil, Plus, Trash2 } from 'lucide-react'
import api from '../../services/api'
import {
  Badge, Card, EmptyState, Field, Modal, PageHeader, Spinner, formatMoney,
  inputClass, primaryButtonClass, secondaryButtonClass,
} from '../ui'

interface Tariff {
  id: string
  name: string
  description: string | null
  currency: string
  base_rate: number
  thresholds: number[]
  rates: number[]
  is_default: boolean
  water_committee_id: string
  household_count: number
}

interface Committee { id: string; name: string }

interface FormState {
  name: string
  description: string
  currency: string
  base_rate: string
  is_default: boolean
  water_committee_id: string
  blocks: { upTo: string; rate: string }[]
}

const emptyForm: FormState = {
  name: '', description: '', currency: 'USD', base_rate: '', is_default: false, water_committee_id: '',
  blocks: [{ upTo: '10', rate: '0' }, { upTo: '15', rate: '' }, { upTo: '20', rate: '' }, { upTo: '', rate: '' }],
}

function toPayload(f: FormState) {
  const thresholds = f.blocks.slice(0, -1).map((b) => Number(b.upTo))
  const rates = f.blocks.map((b) => Number(b.rate || 0))
  return {
    name: f.name, description: f.description || null, currency: f.currency, base_rate: Number(f.base_rate || 0),
    thresholds, rates, is_default: f.is_default, water_committee_id: f.water_committee_id,
  }
}

function charge(t: { base_rate: number; thresholds: number[]; rates: number[] }, m3: number) {
  let lower = 0, remaining = m3, variable = 0
  for (let i = 0; i < t.rates.length; i++) {
    const upper = i < t.thresholds.length ? t.thresholds[i] : null
    const width = upper === null ? remaining : Math.max(0, Math.min(remaining, upper - lower))
    variable += width * t.rates[i]
    remaining -= width
    if (upper === null || remaining <= 0) break
    lower = upper
  }
  return Math.round((t.base_rate + variable) * 100) / 100
}

function describe(t: Tariff) {
  const parts = [`${formatMoney(t.currency, t.base_rate)} base`]
  t.rates.forEach((r, i) => {
    if (i === 0) {
      parts.push(`up to ${t.thresholds[0] ?? '∞'} m³ included`)
    } else {
      const from = t.thresholds[i - 1]
      const to = t.thresholds[i]
      parts.push(`${from}–${to ?? '∞'} m³: ${formatMoney(t.currency, r)}/m³`)
    }
  })
  return parts.join(' · ')
}

export default function TariffsPage() {
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Tariff | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [sample, setSample] = useState('18')

  function load() {
    setLoading(true)
    Promise.all([api.get('/tariffs/'), api.get('/water-committees/')])
      .then(([t, c]) => { setTariffs(t.data); setCommittees(c.data) })
      .catch(() => setTariffs([]))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  function openNew() {
    setEditing(null)
    setForm({ ...emptyForm, water_committee_id: committees[0]?.id ?? '' })
    setError(''); setShowForm(true)
  }
  function openEdit(t: Tariff) {
    setEditing(t)
    setForm({
      name: t.name, description: t.description ?? '', currency: t.currency, base_rate: String(t.base_rate),
      is_default: t.is_default, water_committee_id: t.water_committee_id,
      blocks: t.rates.map((r, i) => ({ upTo: i < t.thresholds.length ? String(t.thresholds[i]) : '', rate: String(r) })),
    })
    setError(''); setShowForm(true)
  }

  const preview = useMemo(() => {
    const p = toPayload(form)
    if (p.thresholds.some((v) => !v || Number.isNaN(v))) return null
    return charge(p, Number(sample || 0))
  }, [form, sample])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true); setError('')
    const payload = toPayload(form)
    const asc = payload.thresholds.every((v, i) => i === 0 || v > payload.thresholds[i - 1])
    if (!asc || payload.thresholds.some((v) => !v)) {
      setError('Block limits must be numbers that increase from one block to the next.'); setSaving(false); return
    }
    try {
      if (editing) await api.patch(`/tariffs/${editing.id}`, payload)
      else await api.post('/tariffs/', payload)
      setShowForm(false); load()
    } catch (err: any) {
      const d = err?.response?.data?.detail
      setError(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join(' ') : 'Could not save the tariff.')
    } finally { setSaving(false) }
  }

  async function remove(t: Tariff) {
    if (!window.confirm(`Delete tariff ${t.name}?`)) return
    try { await api.delete(`/tariffs/${t.id}`); load() }
    catch (err: any) { window.alert(err?.response?.data?.detail ?? 'Could not delete this tariff.') }
  }

  const committeeName = (id: string) => committees.find((c) => c.id === id)?.name ?? '—'

  return (
    <div>
      <PageHeader
        title="Tariffs"
        subtitle="Rising block tariffs set by each water committee. Assign a tariff to a household from its page; the committee's default applies otherwise."
        actions={<button onClick={openNew} className={primaryButtonClass} disabled={committees.length === 0}><Plus className="h-4 w-4" />New tariff</button>}
      />
      {loading ? <Spinner /> : committees.length === 0 ? (
        <EmptyState icon={Calculator} title="Add a water committee first" hint="Tariffs belong to a water committee." />
      ) : tariffs.length === 0 ? (
        <EmptyState icon={Calculator} title="No tariffs yet" hint="Create a standard tariff, and a reduced one for households that need it." />
      ) : (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500"><tr><th className="px-5 py-3">Tariff</th><th className="px-5 py-3">Committee</th><th className="px-5 py-3">Structure</th><th className="px-5 py-3 text-right">Households</th><th className="px-5 py-3"></th></tr></thead>
            <tbody className="divide-y divide-gray-100">
              {tariffs.map((t) => (
                <tr key={t.id}>
                  <td className="px-5 py-3"><div className="flex items-center gap-2 font-medium text-gray-900">{t.name}{t.is_default && <Badge value="default" className="bg-primary-50 text-primary-700" />}</div>{t.description && <p className="text-xs text-gray-500">{t.description}</p>}</td>
                  <td className="px-5 py-3 text-gray-600">{committeeName(t.water_committee_id)}</td>
                  <td className="px-5 py-3 text-gray-600 text-xs">{describe(t)}</td>
                  <td className="px-5 py-3 text-right text-gray-600">{t.household_count}</td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    <button onClick={() => openEdit(t)} className="text-gray-400 hover:text-primary-600 mr-3" title="Edit"><Pencil className="h-4 w-4" /></button>
                    <button onClick={() => remove(t)} className="text-gray-400 hover:text-red-600" title="Delete"><Trash2 className="h-4 w-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {showForm && (
        <Modal title={editing ? 'Edit tariff' : 'New tariff'} onClose={() => setShowForm(false)}>
          <form onSubmit={submit} className="space-y-4">
            {error && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{error}</p>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Standard" /></Field>
              <Field label="Water committee">
                <select className={inputClass} value={form.water_committee_id} onChange={(e) => setForm({ ...form, water_committee_id: e.target.value })} disabled={!!editing}>
                  {committees.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>
              <Field label="Base charge" hint="Charged every bill; covers the first block"><input type="number" step="0.01" min="0" className={inputClass} value={form.base_rate} onChange={(e) => setForm({ ...form, base_rate: e.target.value })} required /></Field>
              <Field label="Currency"><input className={inputClass} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} /></Field>
            </div>
            <Field label="Description" hint="e.g. Reduced rate for elderly households"><input className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Blocks</p>
              <div className="space-y-2">
                {form.blocks.map((b, i) => {
                  const from = i === 0 ? 0 : form.blocks[i - 1].upTo || '?'
                  const last = i === form.blocks.length - 1
                  return (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center text-sm">
                      <span className="col-span-3 text-gray-600">{last ? `Above ${from} m³` : `${from} to`}</span>
                      <div className="col-span-3">{!last && <input type="number" step="0.1" min="0" className={inputClass} placeholder="m³" value={b.upTo} onChange={(e) => { const blocks = [...form.blocks]; blocks[i] = { ...b, upTo: e.target.value }; setForm({ ...form, blocks }) }} required />}</div>
                      <span className="col-span-1 text-gray-500 text-right">{i === 0 ? 'incl.' : 'rate'}</span>
                      <div className="col-span-3"><input type="number" step="0.01" min="0" className={inputClass} placeholder="per m³" value={b.rate} onChange={(e) => { const blocks = [...form.blocks]; blocks[i] = { ...b, rate: e.target.value }; setForm({ ...form, blocks }) }} /></div>
                      <div className="col-span-2 text-right">{form.blocks.length > 1 && !last && <button type="button" className="text-xs text-gray-400 hover:text-red-600" onClick={() => setForm({ ...form, blocks: form.blocks.filter((_, j) => j !== i) })}>remove</button>}</div>
                    </div>
                  )
                })}
              </div>
              <button type="button" className="mt-2 text-xs text-primary-600 hover:underline" onClick={() => { const blocks = [...form.blocks]; blocks.splice(blocks.length - 1, 0, { upTo: '', rate: '' }); setForm({ ...form, blocks }) }}>+ Add a block</button>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />Default tariff for households in this committee without their own</label>
            <div className="rounded-lg bg-gray-50 p-3 text-sm flex items-center gap-3">
              <Calculator className="h-4 w-4 text-gray-400" />
              <span>A household using</span>
              <input type="number" min="0" className={`${inputClass} w-20`} value={sample} onChange={(e) => setSample(e.target.value)} />
              <span>m³ would pay <strong>{preview === null ? '—' : formatMoney(form.currency, preview)}</strong></span>
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
