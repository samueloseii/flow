import { useState } from 'react'
import { ArrowLeft, Check, MessageCircle } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import api from '../../services/api'

interface Props {
  onBack: () => void
}

const categories = [
  { value: 'pipe_repair', label: 'Pipe or leak' },
  { value: 'valve_replacement', label: 'Valve' },
  { value: 'pump_maintenance', label: 'Pump' },
  { value: 'tank_cleaning', label: 'Tank' },
  { value: 'meter_repair', label: 'Meter' },
  { value: 'chlorination', label: 'Chlorination / water quality' },
  { value: 'electrical', label: 'Electrical' },
  { value: 'infrastructure', label: 'Infrastructure' },
  { value: 'other', label: 'Other' },
]

export default function MaintenanceField({ onBack }: Props) {
  const { user } = useAuth()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('other')
  const [whatsapp, setWhatsapp] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [savedCount, setSavedCount] = useState(0)

  async function handleSubmit() {
    if (!title.trim() || !user?.water_committee_id) return
    setSaving(true)
    setError('')
    try {
      await api.post('/maintenance/', {
        title: title.trim(),
        description: description.trim() || null,
        category,
        reported_date: new Date().toISOString(),
        reported_via_whatsapp: whatsapp,
        water_committee_id: user.water_committee_id,
      })
      setTitle('')
      setDescription('')
      setCategory('other')
      setWhatsapp(false)
      setSavedCount((n) => n + 1)
    } catch {
      setError('Could not send the report. Check your connection and try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Report an issue</h1>
          <p className="text-sm text-gray-500">{savedCount} reported this session</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm mb-3">
            {error}
          </div>
        )}

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">What is wrong?</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg text-base focus:ring-2 focus:ring-primary-500"
            placeholder="e.g. Broken pipe by the school"
            autoFocus
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Details (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg text-base focus:ring-2 focus:ring-primary-500"
            placeholder="Where it is, what you saw, how urgent it looks"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Type of issue</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg text-base focus:ring-2 focus:ring-primary-500"
          >
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <label className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-gray-50">
          <input
            type="checkbox"
            checked={whatsapp}
            onChange={(e) => setWhatsapp(e.target.checked)}
            className="mt-0.5 h-5 w-5 rounded border-gray-300 text-primary-600"
          />
          <span className="text-sm text-gray-700">
            <span className="flex items-center gap-1 font-medium">
              <MessageCircle className="h-4 w-4 text-emerald-600" />
              I already told the committee or treasurer on WhatsApp
            </span>
            <span className="block text-gray-500 mt-0.5">
              Send photos there — they are not needed in the app.
            </span>
          </span>
        </label>

        <button
          onClick={handleSubmit}
          disabled={saving || !title.trim()}
          className="w-full py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-base"
        >
          {saving ? (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
          ) : (
            <>
              <Check className="h-5 w-5" />
              Send report
            </>
          )}
        </button>
      </div>

      {savedCount > 0 && (
        <div className="mt-4 text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
          <Check className="h-4 w-4 inline mr-1" />
          Sent to the system administrator.
        </div>
      )}
    </div>
  )
}
