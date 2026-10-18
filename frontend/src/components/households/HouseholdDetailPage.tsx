import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Gauge, Plus, Printer, Receipt } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import api from '../../services/api'
import { Household } from './HouseholdsPage'
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

interface ConsumptionPoint {
  period: string
  consumption_m3: number
}

interface Invoice {
  id: string
  invoice_number: string
  billing_period_start: string
  billing_period_end: string
  consumption_m3: number
  total_amount: number
  amount_paid: number
  balance_due: number
  currency: string
  status: string
  due_date: string
}

interface Payment {
  id: string
  payment_date: string
  amount: number
  currency: string
  payment_method: string
  receipt_number: string | null
  invoice_number: string | null
}

interface Reading {
  id: string
  reading_date: string
  reading_value: number
  previous_value: number
  consumption_m3: number
  flag_reason: string | null
  recorded_by: string | null
  meter_id: string
  invoice_id: string | null
}

interface Meter {
  id: string
  serial_number: string
  brand: string | null
  status: string
  install_date: string | null
  last_reading_value: number
  last_reading_date: string | null
}

interface Tariff {
  id: string
  name: string
  water_committee_id: string
  is_default: boolean
}

interface Detail {
  household: Household
  consumption_history: ConsumptionPoint[]
  invoices: Invoice[]
  payments: Payment[]
  total_billed: number
  total_paid: number
  outstanding: number
  readings: Reading[]
  meters: Meter[]
}

export default function HouseholdDetailPage() {
  const { householdId } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<Detail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [showMeterForm, setShowMeterForm] = useState(false)
  const [meterForm, setMeterForm] = useState({ serial_number: '', brand: '', initial_reading: '0', final_reading_of_old_meter: '', retire_existing_as: 'replaced' })
  const [meterError, setMeterError] = useState('')
  const [savingMeter, setSavingMeter] = useState(false)

  useEffect(() => {
    api.get('/tariffs/').then((r) => setTariffs(r.data)).catch(() => setTariffs([]))
  }, [])

  async function assignTariff(tariffId: string) {
    if (!householdId) return
    try {
      await api.patch(`/households/${householdId}`, tariffId ? { tariff_id: tariffId } : { clear_tariff: true })
      const r = await api.get(`/households/${householdId}/detail`)
      setDetail(r.data)
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not change the tariff.')
    }
  }

  async function submitMeter(e: FormEvent) {
    e.preventDefault()
    if (!householdId) return
    setSavingMeter(true)
    setMeterError('')
    try {
      await api.post('/meters/', {
        household_id: householdId,
        serial_number: meterForm.serial_number,
        brand: meterForm.brand || null,
        initial_reading: Number(meterForm.initial_reading || 0),
        retire_existing_as: meterForm.retire_existing_as,
        final_reading_of_old_meter: meterForm.final_reading_of_old_meter ? Number(meterForm.final_reading_of_old_meter) : null,
      })
      setShowMeterForm(false)
      const r = await api.get(`/households/${householdId}/detail`)
      setDetail(r.data)
    } catch (err: any) {
      setMeterError(err?.response?.data?.detail ?? 'Could not add the meter.')
    } finally {
      setSavingMeter(false)
    }
  }

  useEffect(() => {
    if (!householdId) return
    api
      .get(`/households/${householdId}/detail`, { params: { months: 12 } })
      .then((res) => setDetail(res.data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [householdId])

  if (loading) return <Spinner />

  if (!detail) {
    return (
      <div>
        <button
          onClick={() => navigate('/households')}
          className="flex items-center gap-2 text-sm text-primary-600 mb-6"
        >
          <ArrowLeft className="h-4 w-4" /> Back to households
        </button>
        <EmptyState icon={Receipt} title="Household not found" />
      </div>
    )
  }

  const { household } = detail
  const currency = household.currency

  return (
    <div>
      <button
        onClick={() => navigate('/households')}
        className="flex items-center gap-2 text-sm text-primary-600 mb-4"
      >
        <ArrowLeft className="h-4 w-4" /> Back to households
      </button>

      <PageHeader
        title={household.head_of_household}
        subtitle={`${household.account_number} · ${household.community_name || 'Community'} · meter ${
          household.meter_serial_number || 'not installed'
        }`}
        actions={<Badge value={household.status} />}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard label="Total billed" value={formatMoney(currency, detail.total_billed)} />
        <StatCard
          label="Total paid"
          value={formatMoney(currency, detail.total_paid)}
          tone="positive"
        />
        <StatCard
          label="Outstanding"
          value={formatMoney(currency, detail.outstanding)}
          tone={detail.outstanding > 0 ? 'danger' : 'positive'}
        />
        <StatCard
          label="Last reading"
          value={
            household.last_reading_value != null
              ? `${household.last_reading_value.toFixed(1)} m³`
              : '—'
          }
          hint={formatDate(household.last_reading_date)}
        />
      </div>

      <Card className="p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Consumption, last 12 months</h2>
        <p className="text-sm text-gray-500 mb-4">Cubic metres billed per month.</p>
        {detail.consumption_history.length === 0 ? (
          <EmptyState icon={Receipt} title="No readings recorded yet" />
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={detail.consumption_history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} unit=" m³" width={64} />
                <Tooltip formatter={(value: number) => [`${value} m³`, 'Consumption']} />
                <Bar dataKey="consumption_m3" fill="#0284c7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card className="overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Bills</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr className="text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-6 py-3">Invoice</th>
                <th className="px-6 py-3">Period</th>
                <th className="px-6 py-3 text-right">Consumption</th>
                <th className="px-6 py-3 text-right">Total</th>
                <th className="px-6 py-3 text-right">Balance</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detail.invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-primary-600">
                    {inv.invoice_number}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {formatDate(inv.billing_period_start)} – {formatDate(inv.billing_period_end)}
                  </td>
                  <td className="px-6 py-4 text-sm text-right font-mono">
                    {inv.consumption_m3.toFixed(1)} m³
                  </td>
                  <td className="px-6 py-4 text-sm text-right">
                    {formatMoney(inv.currency, inv.total_amount)}
                  </td>
                  <td className="px-6 py-4 text-sm text-right font-medium">
                    <span className={inv.balance_due > 0 ? 'text-red-600' : 'text-emerald-600'}>
                      {formatMoney(inv.currency, inv.balance_due)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <Badge value={inv.status} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => navigate(`/billing/print?invoice=${inv.id}`)}
                      className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded"
                      title="Print bill"
                    >
                      <Printer className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail.invoices.length === 0 && <EmptyState icon={Receipt} title="No bills issued yet" />}
      </Card>

      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Payments</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr className="text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Invoice</th>
                <th className="px-6 py-3">Method</th>
                <th className="px-6 py-3">Receipt</th>
                <th className="px-6 py-3 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detail.payments.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm">{formatDate(p.payment_date)}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{p.invoice_number || '—'}</td>
                  <td className="px-6 py-4 text-sm capitalize text-gray-500">
                    {p.payment_method.replace(/_/g, ' ')}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{p.receipt_number || '—'}</td>
                  <td className="px-6 py-4 text-sm text-right font-medium text-emerald-600">
                    {formatMoney(p.currency, p.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail.payments.length === 0 && (
          <EmptyState icon={Receipt} title="No payments recorded yet" />
        )}
      </Card>

      <Card className="overflow-hidden mt-8">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Tariff</h2>
            <p className="text-xs text-gray-500">Bills for this household use this tariff; otherwise the committee's default.</p>
          </div>
          <select
            className={`${inputClass} w-64`}
            value={(detail.household as { tariff_id?: string | null }).tariff_id ?? ''}
            onChange={(e) => assignTariff(e.target.value)}
          >
            <option value="">Committee default</option>
            {tariffs.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}{t.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card className="overflow-hidden mt-8">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Meters</h2>
          <button
            className={secondaryButtonClass}
            onClick={() => {
              setMeterForm({ serial_number: '', brand: '', initial_reading: '0', final_reading_of_old_meter: '', retire_existing_as: 'replaced' })
              setMeterError('')
              setShowMeterForm(true)
            }}
          >
            <Plus className="h-4 w-4" />
            {detail.meters.some((m) => m.status === 'active') ? 'Replace meter' : 'Add meter'}
          </button>
        </div>
        {detail.meters.length === 0 ? (
          <div className="p-6"><EmptyState icon={Gauge} title="No meter" hint="Add a meter so operators can record readings." /></div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500">
              <tr><th className="px-6 py-3">Serial</th><th className="px-6 py-3">Brand</th><th className="px-6 py-3">Status</th><th className="px-6 py-3">Installed</th><th className="px-6 py-3 text-right">Last reading</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detail.meters.map((m) => (
                <tr key={m.id}>
                  <td className="px-6 py-3 font-mono text-xs text-gray-900">{m.serial_number}</td>
                  <td className="px-6 py-3 text-gray-600">{m.brand ?? '—'}</td>
                  <td className="px-6 py-3"><Badge value={m.status} className={m.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'} /></td>
                  <td className="px-6 py-3 text-gray-600">{formatDate(m.install_date)}</td>
                  <td className="px-6 py-3 text-right text-gray-900">{m.last_reading_value}{m.last_reading_date ? <span className="text-xs text-gray-500"> · {formatDate(m.last_reading_date)}</span> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="overflow-hidden mt-8">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Meter readings</h2>
          <p className="text-xs text-gray-500">Raw readings as recorded, newest first, and the bill each went into.</p>
        </div>
        {detail.readings.length === 0 ? (
          <div className="p-6 text-sm text-gray-500">No readings recorded yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500">
              <tr><th className="px-6 py-3">Date</th><th className="px-6 py-3">Meter</th><th className="px-6 py-3 text-right">Previous</th><th className="px-6 py-3 text-right">Reading</th><th className="px-6 py-3 text-right">Used m³</th><th className="px-6 py-3">Status</th><th className="px-6 py-3">Recorded by</th><th className="px-6 py-3">Bill</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detail.readings.map((r) => {
                const bill = detail.invoices.find((i) => i.id === r.invoice_id)
                const meter = detail.meters.find((m) => m.id === r.meter_id)
                return (
                  <tr key={r.id} className={r.flag_reason ? 'bg-amber-50/40' : ''}>
                    <td className="px-6 py-3 text-gray-600">{formatDate(r.reading_date)}</td>
                    <td className="px-6 py-3 font-mono text-xs text-gray-600">{meter?.serial_number ?? '—'}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{r.previous_value}</td>
                    <td className="px-6 py-3 text-right font-medium text-gray-900">{r.reading_value}</td>
                    <td className="px-6 py-3 text-right">{r.consumption_m3}</td>
                    <td className="px-6 py-3">{r.flag_reason ? <Badge value={r.flag_reason} className="bg-amber-100 text-amber-800" /> : <Badge value="ok" className="bg-green-50 text-green-700" />}</td>
                    <td className="px-6 py-3 text-gray-600">{r.recorded_by ?? '—'}</td>
                    <td className="px-6 py-3 text-gray-600">{bill ? bill.invoice_number : <span className="text-gray-400">not billed</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>

      {showMeterForm && (
        <Modal title={detail.meters.some((m) => m.status === 'active') ? 'Replace meter' : 'Add meter'} onClose={() => setShowMeterForm(false)}>
          <form onSubmit={submitMeter} className="space-y-4">
            {meterError && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{meterError}</p>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="New meter serial number"><input className={inputClass} value={meterForm.serial_number} onChange={(e) => setMeterForm({ ...meterForm, serial_number: e.target.value })} required /></Field>
              <Field label="Brand"><input className={inputClass} value={meterForm.brand} onChange={(e) => setMeterForm({ ...meterForm, brand: e.target.value })} /></Field>
              <Field label="Reading on the new meter" hint="Usually 0"><input type="number" step="0.1" min="0" className={inputClass} value={meterForm.initial_reading} onChange={(e) => setMeterForm({ ...meterForm, initial_reading: e.target.value })} /></Field>
              {detail.meters.some((m) => m.status === 'active') && (
                <>
                  <Field label="Final reading on the old meter" hint="Optional; recorded before it is retired"><input type="number" step="0.1" min="0" className={inputClass} value={meterForm.final_reading_of_old_meter} onChange={(e) => setMeterForm({ ...meterForm, final_reading_of_old_meter: e.target.value })} /></Field>
                  <Field label="Old meter becomes">
                    <select className={inputClass} value={meterForm.retire_existing_as} onChange={(e) => setMeterForm({ ...meterForm, retire_existing_as: e.target.value })}>
                      <option value="replaced">Replaced</option>
                      <option value="removed">Removed</option>
                      <option value="faulty">Faulty</option>
                    </select>
                  </Field>
                </>
              )}
            </div>
            <p className="text-xs text-gray-500">Readings on the old meter stay in the history. Operators will only see the new meter.</p>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setShowMeterForm(false)}>Cancel</button>
              <button type="submit" className={primaryButtonClass} disabled={savingMeter}>{savingMeter ? 'Saving…' : 'Save'}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
