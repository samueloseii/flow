import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DollarSign, FilePlus2, Printer, Receipt, Search, Trash2 } from 'lucide-react'
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
  StatCard,
  formatDate,
  formatMoney,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui'

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
  connection_id: string
  connection_name: string | null
  account_number: string | null
}

interface Payment {
  id: string
  payment_date: string
  amount: number
  currency: string
  payment_method: string
  receipt_number: string | null
  connection_name: string | null
  account_number: string | null
  invoice_number: string | null
}

interface Community {
  id: string
  name: string
}

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10)
}

function defaultPeriod() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const end = new Date(now.getFullYear(), now.getMonth(), 0)
  const due = new Date(now.getFullYear(), now.getMonth(), 15)
  return { start: isoDate(start), end: isoDate(end), due: isoDate(due) }
}

export default function BillingPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canRecord = ['super_admin', 'admin', 'editor'].includes(user?.role ?? '')
  const canDelete = ['super_admin', 'admin'].includes(user?.role ?? '')
  const [tab, setTab] = useState<'invoices' | 'payments'>('invoices')
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [unpaidOnly, setUnpaidOnly] = useState(false)
  const [communityId, setCommunityId] = useState('')
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')

  const [showGenerate, setShowGenerate] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState('')
  const [generateResult, setGenerateResult] = useState('')
  const [genForm, setGenForm] = useState({ community_id: '', ...defaultPeriod() })

  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null)
  const [payForm, setPayForm] = useState({ amount: '', receipt_number: '', method: 'cash', date: isoDate(new Date()) })
  const [payError, setPayError] = useState('')
  const [payingBusy, setPayingBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const params: Record<string, string | boolean> = {}
    if (search.trim()) params.search = search.trim()
    if (unpaidOnly) params.unpaid_only = true
    if (communityId) params.community_id = communityId
    if (periodStart) params.period_start = new Date(periodStart).toISOString()
    if (periodEnd) params.period_end = new Date(periodEnd).toISOString()
    try {
      const [invRes, payRes] = await Promise.all([
        api.get('/billing/invoices', { params: { ...params, limit: 500 } }),
        api.get('/billing/payments', {
          params: { limit: 500, ...(communityId ? { community_id: communityId } : {}) },
        }),
      ])
      setInvoices(invRes.data)
      setPayments(payRes.data)
    } catch {
      setInvoices([])
      setPayments([])
    } finally {
      setLoading(false)
    }
  }, [search, unpaidOnly, communityId, periodStart, periodEnd])

  useEffect(() => {
    const timer = setTimeout(load, 250)
    return () => clearTimeout(timer)
  }, [load])

  useEffect(() => {
    api
      .get('/communities/')
      .then((res) => setCommunities(res.data))
      .catch(() => setCommunities([]))
  }, [])

  async function deleteInvoice(invoice: Invoice) {
    if (!window.confirm(`Delete bill ${invoice.invoice_number}?`)) return
    try {
      await api.delete(`/billing/invoices/${invoice.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not delete this bill.')
    }
  }

  async function deletePayment(payment: Payment) {
    if (!window.confirm('Delete this payment and restore the balance it settled?')) return
    try {
      await api.delete(`/billing/payments/${payment.id}`)
      load()
    } catch (err: any) {
      window.alert(err?.response?.data?.detail ?? 'Could not delete this payment.')
    }
  }

  async function handleGenerate(e: FormEvent) {
    e.preventDefault()
    setGenerating(true)
    setGenerateError('')
    setGenerateResult('')
    try {
      const res = await api.post('/billing/invoices/generate', {
        community_id: genForm.community_id,
        billing_period_start: new Date(genForm.start).toISOString(),
        billing_period_end: new Date(genForm.end).toISOString(),
        due_date: new Date(genForm.due).toISOString(),
      })
      setGenerateResult(
        `${res.data.created} bill(s) created · ${res.data.skipped_existing} already billed · ${res.data.skipped_no_reading} without a reading`,
      )
      await load()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setGenerateError(detail || 'Could not generate bills for that period.')
    } finally {
      setGenerating(false)
    }
  }

  async function handlePayment(e: FormEvent) {
    e.preventDefault()
    if (!payingInvoice) return
    setPayingBusy(true)
    setPayError('')
    try {
      await api.post('/billing/payments', {
        amount: Number(payForm.amount),
        currency: payingInvoice.currency,
        payment_method: payForm.method,
        payment_date: new Date(payForm.date).toISOString(),
        receipt_number: payForm.receipt_number || null,
        connection_id: payingInvoice.connection_id,
        invoice_id: payingInvoice.id,
      })
      setPayingInvoice(null)
      await load()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setPayError(detail || 'Could not record the payment.')
    } finally {
      setPayingBusy(false)
    }
  }

  const outstanding = invoices.reduce((sum, inv) => sum + inv.balance_due, 0)
  const unpaidCount = invoices.filter((inv) => inv.balance_due > 0).length
  const overdueCount = invoices.filter((inv) => inv.status === 'overdue').length
  const collected = payments.reduce((sum, p) => sum + p.amount, 0)
  const billedConsumption = invoices.reduce((sum, inv) => sum + inv.consumption_m3, 0)

  return (
    <div>
      <PageHeader
        title="Billing"
        subtitle="Bills by connection, with the consumption they were charged for."
        actions={
          <button
            onClick={() => {
              setGenForm({ community_id: communityId, ...defaultPeriod() })
              setGenerateError('')
              setGenerateResult('')
              setShowGenerate(true)
            }}
            className={primaryButtonClass}
          >
            <FilePlus2 className="h-4 w-4" />
            Generate bills
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <StatCard label="Collected" value={collected.toFixed(2)} hint={`${payments.length} payments`} tone="positive" />
        <StatCard
          label="Unpaid bills"
          value={unpaidCount}
          hint={overdueCount ? `${overdueCount} overdue` : 'none overdue'}
          tone={overdueCount ? 'danger' : unpaidCount ? 'warning' : 'positive'}
        />
        <StatCard
          label="Outstanding"
          value={outstanding.toFixed(2)}
          hint={`${billedConsumption.toFixed(1)} m³ billed`}
          tone={outstanding > 0 ? 'danger' : 'positive'}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-6">
        <button
          onClick={() => setTab('invoices')}
          className={`${tab === 'invoices' ? primaryButtonClass : secondaryButtonClass}`}
        >
          <Receipt className="h-4 w-4" /> Bills
        </button>
        <button
          onClick={() => setTab('payments')}
          className={`${tab === 'payments' ? primaryButtonClass : secondaryButtonClass}`}
        >
          <DollarSign className="h-4 w-4" /> Payments
        </button>
      </div>

      {tab === 'invoices' && (
        <Card className="p-4 mb-6">
          <div className="grid gap-3 md:grid-cols-5">
            <div className="relative md:col-span-2">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Connection, account or invoice no."
                className={`${inputClass} pl-9`}
              />
            </div>
            <select
              value={communityId}
              onChange={(e) => setCommunityId(e.target.value)}
              className={inputClass}
            >
              <option value="">All communities</option>
              {communities.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className={inputClass}
              title="Period from"
            />
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className={inputClass}
              title="Period to"
            />
          </div>
          <label className="flex items-center gap-2 mt-3 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={unpaidOnly}
              onChange={(e) => setUnpaidOnly(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-primary-600"
            />
            Show only connections that still owe money
          </label>
        </Card>
      )}

      {loading ? (
        <Spinner />
      ) : tab === 'invoices' ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr className="text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-6 py-3">Connection</th>
                  <th className="px-6 py-3">Period</th>
                  <th className="px-6 py-3 text-right">Consumption</th>
                  <th className="px-6 py-3 text-right">Total</th>
                  <th className="px-6 py-3 text-right">Balance</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => navigate(`/connections/${inv.connection_id}`)}
                        className="font-medium text-primary-600 hover:underline"
                      >
                        {inv.connection_name || 'Unknown connection'}
                      </button>
                      <span className="block text-xs text-gray-400">
                        {inv.account_number} · {inv.invoice_number}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatDate(inv.billing_period_start)} – {formatDate(inv.billing_period_end)}
                      <span className="block text-xs text-gray-400">
                        due {formatDate(inv.due_date)}
                      </span>
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
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      {canRecord && inv.balance_due > 0 && (
                        <button
                          onClick={() => {
                            setPayingInvoice(inv)
                            setPayForm({
                              amount: inv.balance_due.toFixed(2),
                              receipt_number: '',
                              method: 'cash',
                              date: isoDate(new Date()),
                            })
                            setPayError('')
                          }}
                          className="px-2.5 py-1 mr-1 text-xs font-medium rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        >
                          Record payment
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/billing/print?invoice=${inv.id}`)}
                        className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded"
                        title="Print bill"
                      >
                        <Printer className="h-4 w-4" />
                      </button>
                      {canDelete && <button
                        onClick={() => deleteInvoice(inv)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete bill"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {invoices.length === 0 && (
            <EmptyState
              icon={Receipt}
              title="No bills match these filters"
              hint="Generate bills for a billing period to get started."
            />
          )}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr className="text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Connection</th>
                  <th className="px-6 py-3">Invoice</th>
                  <th className="px-6 py-3">Method</th>
                  <th className="px-6 py-3">Receipt</th>
                  <th className="px-6 py-3 text-right">Amount</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {payments.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm">{formatDate(p.payment_date)}</td>
                    <td className="px-6 py-4 text-sm">
                      {p.connection_name || '—'}
                      <span className="block text-xs text-gray-400">{p.account_number}</span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{p.invoice_number || '—'}</td>
                    <td className="px-6 py-4 text-sm capitalize text-gray-500">
                      {p.payment_method.replace(/_/g, ' ')}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{p.receipt_number || '—'}</td>
                    <td className="px-6 py-4 text-sm text-right font-medium text-emerald-600">
                      {formatMoney(p.currency, p.amount)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {canDelete && <button
                        onClick={() => deletePayment(p)}
                        className="p-1.5 text-gray-300 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete payment"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {payments.length === 0 && <EmptyState icon={DollarSign} title="No payments recorded" />}
        </Card>
      )}

      {showGenerate && (
        <Modal
          title="Generate bills"
          description="Bills every active connection in the community using the readings recorded in the period."
          onClose={() => setShowGenerate(false)}
        >
          <form onSubmit={handleGenerate} className="space-y-4">
            {generateError && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm">
                {generateError}
              </div>
            )}
            {generateResult && (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg px-4 py-3 text-sm">
                {generateResult}
              </div>
            )}
            <Field label="Community">
              <select
                required
                value={genForm.community_id}
                onChange={(e) => setGenForm({ ...genForm, community_id: e.target.value })}
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
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Period from">
                <input
                  type="date"
                  required
                  value={genForm.start}
                  onChange={(e) => setGenForm({ ...genForm, start: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Period to">
                <input
                  type="date"
                  required
                  value={genForm.end}
                  onChange={(e) => setGenForm({ ...genForm, end: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Due date">
                <input
                  type="date"
                  required
                  value={genForm.due}
                  onChange={(e) => setGenForm({ ...genForm, due: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowGenerate(false)}
                className={secondaryButtonClass}
              >
                Close
              </button>
              <button type="submit" disabled={generating} className={primaryButtonClass}>
                {generating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {payingInvoice && (
        <Modal
          title="Record payment"
          description={`${payingInvoice.connection_name} · ${payingInvoice.invoice_number}`}
          onClose={() => setPayingInvoice(null)}
        >
          <form onSubmit={handlePayment} className="space-y-4">
            {payError && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm">
                {payError}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Date paid">
                <input
                  type="date"
                  required
                  value={payForm.date}
                  onChange={(e) => setPayForm({ ...payForm, date: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label={`Amount (${payingInvoice.currency})`}>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={payForm.amount}
                  onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Method">
                <select
                  value={payForm.method}
                  onChange={(e) => setPayForm({ ...payForm, method: e.target.value })}
                  className={inputClass}
                >
                  <option value="cash">Cash</option>
                  <option value="mobile_money">Mobile money</option>
                  <option value="bank_transfer">Bank transfer</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              <Field label="Receipt no.">
                <input
                  value={payForm.receipt_number}
                  onChange={(e) => setPayForm({ ...payForm, receipt_number: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPayingInvoice(null)}
                className={secondaryButtonClass}
              >
                Cancel
              </button>
              <button type="submit" disabled={payingBusy} className={primaryButtonClass}>
                {payingBusy ? 'Saving...' : 'Record payment'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
