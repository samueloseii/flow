import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Droplets, Printer } from 'lucide-react'
import api from '../../services/api'

interface BillDetail {
  connection_name: string
  account_number: string
  community_name: string
  country: string
  currency: string
  invoice_number: string
  period: string
  consumption_m3: number
  fixed_charge: number
  variable_charge: number
  total_amount: number
  amount_paid: number
  balance_due: number
  status: string
  due_date: string
  previous_reading: number | null
  current_reading: number | null
}

export default function PrintBill() {
  const [params] = useSearchParams()
  const invoiceId = params.get('invoice')
  const [bill, setBill] = useState<BillDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!invoiceId) return
    api
      .get(`/billing/bill/${invoiceId}`)
      .then((res) => setBill(res.data))
      .catch(() => setBill(null))
      .finally(() => setLoading(false))
  }, [invoiceId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (!bill) {
    return <div className="text-center py-12 text-gray-500">Bill not found</div>
  }

  return (
    <div>
      <div className="print:hidden mb-4 flex justify-end">
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          <Printer className="h-4 w-4" />
          Print Bill
        </button>
      </div>

      <div className="max-w-2xl mx-auto bg-white border border-gray-200 rounded-lg p-8 print:border-none print:shadow-none print:p-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-4 mb-6">
          <div className="flex items-center gap-3">
            <Droplets className="h-8 w-8 text-primary-600" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">Flow</h1>
              <p className="text-xs text-gray-500">Community Water Management</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium">{bill.community_name}</p>
            <p className="text-xs text-gray-500">{bill.country}</p>
          </div>
        </div>

        {/* Bill info */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <p className="text-xs text-gray-500">Bill To</p>
            <p className="font-semibold">{bill.connection_name}</p>
            <p className="text-sm text-gray-600">Account: {bill.account_number}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-500">Invoice</p>
            <p className="font-semibold">{bill.invoice_number}</p>
            <p className="text-sm text-gray-600">Due: {bill.due_date}</p>
          </div>
        </div>

        {/* Period & Readings */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <p className="text-sm font-medium text-gray-700 mb-2">Billing Period: {bill.period}</p>
          {bill.previous_reading != null && bill.current_reading != null && (
            <div className="flex gap-8 text-sm">
              <div>
                <span className="text-gray-500">Previous reading: </span>
                <span className="font-mono font-medium">{bill.previous_reading.toFixed(1)} m³</span>
              </div>
              <div>
                <span className="text-gray-500">Current reading: </span>
                <span className="font-mono font-medium">{bill.current_reading.toFixed(1)} m³</span>
              </div>
              <div>
                <span className="text-gray-500">Consumption: </span>
                <span className="font-mono font-bold">{bill.consumption_m3.toFixed(1)} m³</span>
              </div>
            </div>
          )}
        </div>

        {/* Charges */}
        <table className="w-full mb-6">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 text-sm text-gray-500">Description</th>
              <th className="text-right py-2 text-sm text-gray-500">Amount ({bill.currency})</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100">
              <td className="py-2 text-sm">Fixed charge (base tariff)</td>
              <td className="py-2 text-sm text-right font-mono">{bill.fixed_charge.toFixed(2)}</td>
            </tr>
            <tr className="border-b border-gray-100">
              <td className="py-2 text-sm">Variable charge ({bill.consumption_m3.toFixed(1)} m³)</td>
              <td className="py-2 text-sm text-right font-mono">{bill.variable_charge.toFixed(2)}</td>
            </tr>
            <tr className="border-b border-gray-200 font-semibold">
              <td className="py-2 text-sm">Total</td>
              <td className="py-2 text-sm text-right font-mono">{bill.total_amount.toFixed(2)}</td>
            </tr>
            {bill.amount_paid > 0 && (
              <tr className="border-b border-gray-100 text-green-700">
                <td className="py-2 text-sm">Amount paid</td>
                <td className="py-2 text-sm text-right font-mono">-{bill.amount_paid.toFixed(2)}</td>
              </tr>
            )}
            <tr className="font-bold text-lg">
              <td className="py-3">Balance Due</td>
              <td className="py-3 text-right font-mono">{bill.currency} {bill.balance_due.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>

        {/* Status */}
        <div className="text-center text-sm text-gray-500 border-t border-gray-200 pt-4">
          <p>Please present this bill at your community water committee office on payment day.</p>
          <p className="mt-1">Thank you for conserving water.</p>
        </div>
      </div>
    </div>
  )
}
