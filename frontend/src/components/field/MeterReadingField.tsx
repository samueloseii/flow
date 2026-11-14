import { useEffect, useState } from 'react'
import { ArrowLeft, AlertTriangle, Check, Wifi, WifiOff } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import api from '../../services/api'
import { saveOfflineReading, getPendingReadings } from '../../services/offlineStore'

interface ReadingContext {
  connection_id: string
  account_number: string
  contact_name: string
  address: string | null
  community_id: string
  meter_id: string
  serial_number: string
  last_reading_value: number
  last_reading_date: string | null
  avg_consumption_m3: number
}

interface Props {
  onBack: () => void
}

// Mirrors the backend anomaly rules so the operator sees the warning before saving.
const HIGH_CONSUMPTION_RATIO = 1.25

function warningFor(target: ReadingContext, value: number): string {
  const previous = target.last_reading_value
  if (value < previous) {
    return `This reading (${value}) is lower than the last one (${previous.toFixed(
      1,
    )}). Meters only count up — check for a transposed digit.`
  }
  const consumption = value - previous
  if (consumption === 0) {
    return 'No consumption since the last reading. Confirm the meter is working and the house is occupied.'
  }
  const average = target.avg_consumption_m3
  if (average > 0 && consumption > average * HIGH_CONSUMPTION_RATIO) {
    return `Consumption of ${consumption.toFixed(1)} m³ is well above this connection's usual ${average.toFixed(
      1,
    )} m³. Re-read the dial or note a possible leak.`
  }
  return ''
}

export default function MeterReadingField({ onBack }: Props) {
  const { user } = useAuth()
  const [targets, setTargets] = useState<ReadingContext[]>([])
  const [selected, setSelected] = useState('')
  const [readingValue, setReadingValue] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<string[]>([])
  const [online, setOnline] = useState(navigator.onLine)
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  useEffect(() => {
    getPendingReadings().then((r) => setPendingCount(r.length))
  }, [saved])

  useEffect(() => {
    api
      .get('/meters/reading-context', {
        params: user?.community_id ? { community_id: user.community_id } : {},
      })
      .then((res) => setTargets(res.data))
      .catch(() => setTargets([]))
  }, [user?.community_id])

  const target = targets.find((t) => t.connection_id === selected) || null
  const value = parseFloat(readingValue)
  const hasValue = readingValue !== '' && !Number.isNaN(value)
  const warning = target && hasValue ? warningFor(target, value) : ''
  const consumption = target && hasValue ? Math.max(0, value - target.last_reading_value) : 0

  async function handleSubmit() {
    if (!target || !hasValue) return
    setSaving(true)
    const reading = {
      client_id: `r-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      meter_id: target.meter_id,
      reading_value: value,
      reading_date: new Date().toISOString(),
      notes: notes || undefined,
      recorded_by: user?.full_name || 'Unknown',
    }

    let synced = false
    if (online) {
      try {
        await api.post('/sync/push', { readings: [reading], payments: [] })
        synced = true
      } catch {
        synced = false
      }
    }
    if (!synced) {
      await saveOfflineReading(reading)
    }

    setTargets((prev) =>
      prev.map((t) =>
        t.connection_id === target.connection_id && value >= t.last_reading_value
          ? { ...t, last_reading_value: value, last_reading_date: reading.reading_date }
          : t,
      ),
    )
    setSaved((prev) => [...prev, target.connection_id])
    setSelected('')
    setReadingValue('')
    setNotes('')
    setSaving(false)
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Meter readings</h1>
          <p className="text-sm text-gray-500">{saved.length} recorded this session</p>
        </div>
      </div>

      <div
        className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm mb-4 ${
          online ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
        }`}
      >
        <div className="flex items-center gap-2">
          {online ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
          {online ? 'Online' : 'Offline — saving locally'}
        </div>
        {pendingCount > 0 && (
          <span className="bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full text-xs font-medium">
            {pendingCount} pending sync
          </span>
        )}
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Connection</label>
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value)
            setReadingValue('')
            setNotes('')
          }}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg text-base focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">— Choose connection —</option>
          {targets.map((t) => (
            <option key={t.connection_id} value={t.connection_id}>
              {t.account_number} — {t.contact_name} {saved.includes(t.connection_id) ? '✓' : ''}
            </option>
          ))}
        </select>
        {targets.length === 0 && (
          <p className="text-sm text-gray-500 mt-2">
            No metered connections assigned yet. Ask your administrator to register them.
          </p>
        )}
      </div>

      {target && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
          <div className="grid grid-cols-2 gap-3 mb-4 pb-3 border-b border-gray-100">
            <div>
              <p className="text-sm text-gray-500">Previous reading</p>
              <p className="text-lg font-bold font-mono">
                {target.last_reading_value.toFixed(1)} m³
              </p>
              <p className="text-xs text-gray-400">
                {target.last_reading_date
                  ? new Date(target.last_reading_date).toLocaleDateString()
                  : 'No reading yet'}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Meter</p>
              <p className="text-sm font-medium">{target.serial_number}</p>
              <p className="text-xs text-gray-400">
                usual {target.avg_consumption_m3.toFixed(1)} m³/month
              </p>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              New reading (m³) — the number on the dial
            </label>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={readingValue}
              onChange={(e) => setReadingValue(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg text-xl font-mono focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder={`> ${target.last_reading_value.toFixed(1)}`}
              autoFocus
            />
          </div>

          {hasValue && (
            <div className="bg-blue-50 rounded-lg px-3 py-2 mb-3 text-sm text-blue-700">
              Consumption this period: <strong>{consumption.toFixed(1)} m³</strong>
            </div>
          )}

          {warning && (
            <div className="flex items-start gap-2 bg-amber-50 rounded-lg px-3 py-2 mb-3 text-sm text-amber-800">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                {warning}
                <span className="block text-xs text-amber-600 mt-1">
                  You can still save it — the reading will be flagged for review.
                </span>
              </span>
            </div>
          )}

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm"
              placeholder="e.g. Dial hard to read, estimated"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={saving || !hasValue}
            className="w-full py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-base"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
            ) : (
              <>
                <Check className="h-5 w-5" />
                Save reading
              </>
            )}
          </button>
        </div>
      )}

      {saved.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Recorded this session</h3>
          <div className="space-y-1">
            {saved.map((connectionId, index) => {
              const item = targets.find((t) => t.connection_id === connectionId)
              return (
                <div
                  key={`${connectionId}-${index}`}
                  className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2"
                >
                  <Check className="h-4 w-4" />
                  {item?.account_number} — {item?.contact_name}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
