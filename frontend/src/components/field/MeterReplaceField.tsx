import { useEffect, useState } from 'react'
import { ArrowLeft, Check } from 'lucide-react'
import api from '../../services/api'

interface Target {
  household_id: string
  account_number: string
  head_of_household: string
  community_name: string
  meter_id: string | null
  serial_number: string | null
  last_reading_value: number
}

interface Props {
  onBack: () => void
}

// Operators can fit a new meter in the field: the old one is retired with its final
// reading kept, and the new serial becomes the active meter for future readings.
export default function MeterReplaceField({ onBack }: Props) {
  const [households, setHouseholds] = useState<Target[]>([])
  const [selected, setSelected] = useState('')
  const [serial, setSerial] = useState('')
  const [brand, setBrand] = useState('')
  const [initialReading, setInitialReading] = useState('0')
  const [finalReading, setFinalReading] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')

  function load() {
    // Households without an active meter are not in reading-context, so merge both lists.
    Promise.all([api.get('/households/'), api.get('/communities/'), api.get('/meters/reading-context')])
      .then(([hhRes, commRes, ctxRes]) => {
        const communityName = new Map<string, string>(commRes.data.map((c: any) => [c.id, c.name]))
        const metered = new Map<string, any>(ctxRes.data.map((t: any) => [t.household_id, t]))
        setHouseholds(
          hhRes.data.map((h: any): Target => {
            const ctx = metered.get(h.id)
            return {
              household_id: h.id,
              account_number: h.account_number,
              head_of_household: h.head_of_household,
              community_name: communityName.get(h.community_id) ?? '',
              meter_id: ctx?.meter_id ?? null,
              serial_number: ctx?.serial_number ?? null,
              last_reading_value: ctx?.last_reading_value ?? 0,
            }
          }),
        )
      })
      .catch(() => setHouseholds([]))
  }
  useEffect(load, [])

  const target = households.find((h) => h.household_id === selected) || null
  const hasOldMeter = !!target?.meter_id

  async function submit() {
    if (!target || !serial.trim()) return
    setSaving(true)
    setError('')
    try {
      await api.post('/meters/', {
        household_id: target.household_id,
        serial_number: serial.trim(),
        brand: brand.trim() || undefined,
        initial_reading: parseFloat(initialReading) || 0,
        final_reading_of_old_meter: hasOldMeter && finalReading !== '' ? parseFloat(finalReading) : undefined,
      })
      setDone(`${serial.trim()} is now the active meter for ${target.head_of_household}.`)
      setSelected('')
      setSerial('')
      setBrand('')
      setInitialReading('0')
      setFinalReading('')
      load()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save the meter. You need to be online for this.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100"><ArrowLeft className="h-5 w-5" /></button>
        <h1 className="text-lg font-semibold text-gray-900">Add or replace a meter</h1>
      </div>

      {done && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
          <Check className="h-4 w-4" />{done}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-100 p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Household</label>
          <select className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm" value={selected} onChange={(e) => { setSelected(e.target.value); setDone('') }}>
            <option value="">Choose a household</option>
            {households.map((h) => (
              <option key={h.household_id} value={h.household_id}>
                {h.account_number} — {h.head_of_household} ({h.community_name}){h.serial_number ? ` · meter ${h.serial_number}` : ' · no meter'}
              </option>
            ))}
          </select>
        </div>

        {target && (
          <>
            {hasOldMeter ? (
              <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                Current meter <span className="font-medium">{target.serial_number}</span>, last reading {target.last_reading_value.toFixed(1)}. It will be marked as replaced and its readings kept.
              </div>
            ) : (
              <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">This household has no active meter yet.</div>
            )}
            {hasOldMeter && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Final reading on the old meter (optional)</label>
                <input type="number" inputMode="decimal" min={target.last_reading_value} step="0.1" className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm" value={finalReading} onChange={(e) => setFinalReading(e.target.value)} placeholder={`At least ${target.last_reading_value.toFixed(1)}`} />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New meter serial number</label>
              <input className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm" value={serial} onChange={(e) => setSerial(e.target.value)} placeholder="As printed on the meter" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Brand (optional)</label>
                <input className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm" value={brand} onChange={(e) => setBrand(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reading on the new meter</label>
                <input type="number" inputMode="decimal" min={0} step="0.1" className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm" value={initialReading} onChange={(e) => setInitialReading(e.target.value)} />
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button onClick={submit} disabled={saving || !serial.trim()} className="w-full py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 text-base">
              {saving ? 'Saving…' : hasOldMeter ? 'Replace meter' : 'Add meter'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
