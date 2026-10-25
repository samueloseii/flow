import { useEffect, useState } from 'react'
import { ArrowLeft, Check } from 'lucide-react'
import api from '../../services/api'

interface CommunityOption {
  id: string
  name: string
}

interface Props {
  onBack: () => void
}

// Operators register a new water account in a community they cover. A meter can be
// fitted at the same time so the first reading is checked against it.
export default function HouseholdAddField({ onBack }: Props) {
  const [communities, setCommunities] = useState<CommunityOption[]>([])
  const [form, setForm] = useState({
    community_id: '',
    account_number: '',
    head_of_household: '',
    phone: '',
    address: '',
    members_count: '1',
    meter_serial_number: '',
    meter_initial_reading: '0',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')

  useEffect(() => {
    api
      .get('/communities/')
      .then((res) => {
        setCommunities(res.data)
        if (res.data.length === 1) setForm((f) => ({ ...f, community_id: res.data[0].id }))
      })
      .catch(() => setCommunities([]))
  }, [])

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const ready = form.community_id && form.account_number.trim() && form.head_of_household.trim()

  async function submit() {
    if (!ready) return
    setSaving(true)
    setError('')
    try {
      await api.post('/households/', {
        community_id: form.community_id,
        account_number: form.account_number.trim(),
        head_of_household: form.head_of_household.trim(),
        phone: form.phone.trim() || undefined,
        address: form.address.trim() || undefined,
        members_count: parseInt(form.members_count, 10) || 1,
        meter_serial_number: form.meter_serial_number.trim() || undefined,
        meter_initial_reading: parseFloat(form.meter_initial_reading) || 0,
      })
      setDone(`${form.head_of_household.trim()} (${form.account_number.trim()}) is registered${form.meter_serial_number.trim() ? ` with meter ${form.meter_serial_number.trim()}` : ''}.`)
      setForm((f) => ({ ...f, account_number: '', head_of_household: '', phone: '', address: '', members_count: '1', meter_serial_number: '', meter_initial_reading: '0' }))
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the household. You need to be online for this.')
    } finally {
      setSaving(false)
    }
  }

  const input = 'w-full px-4 py-2 border border-gray-300 rounded-lg text-sm'
  const label = 'block text-sm font-medium text-gray-700 mb-1'

  return (
    <div className="max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100"><ArrowLeft className="h-5 w-5" /></button>
        <h1 className="text-lg font-semibold text-gray-900">Register a household</h1>
      </div>

      {done && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
          <Check className="h-4 w-4" />{done}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-100 p-4 space-y-4">
        <div>
          <label className={label}>Community</label>
          <select className={input} value={form.community_id} onChange={set('community_id')}>
            <option value="">Choose a community</option>
            {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={label}>Account number</label>
            <input className={input} value={form.account_number} onChange={set('account_number')} placeholder="e.g. A-012" />
          </div>
          <div>
            <label className={label}>People in household</label>
            <input type="number" inputMode="numeric" min={1} className={input} value={form.members_count} onChange={set('members_count')} />
          </div>
        </div>
        <div>
          <label className={label}>Head of household</label>
          <input className={input} value={form.head_of_household} onChange={set('head_of_household')} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={label}>Phone (optional)</label>
            <input inputMode="tel" className={input} value={form.phone} onChange={set('phone')} />
          </div>
          <div>
            <label className={label}>Address (optional)</label>
            <input className={input} value={form.address} onChange={set('address')} />
          </div>
        </div>
        <div className="border-t border-gray-100 pt-4 grid grid-cols-2 gap-3">
          <div>
            <label className={label}>Meter serial number (optional)</label>
            <input className={input} value={form.meter_serial_number} onChange={set('meter_serial_number')} placeholder="As printed on the meter" />
          </div>
          <div>
            <label className={label}>Reading on the meter now</label>
            <input type="number" inputMode="decimal" min={0} step="0.1" className={input} value={form.meter_initial_reading} onChange={set('meter_initial_reading')} disabled={!form.meter_serial_number.trim()} />
          </div>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={submit} disabled={saving || !ready} className="w-full py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 text-base">
          {saving ? 'Saving…' : 'Register household'}
        </button>
      </div>
    </div>
  )
}
