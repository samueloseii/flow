import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Gauge, Upload } from 'lucide-react'
import api from '../../services/api'
import {
  Badge, Card, EmptyState, Field, Modal, PageHeader, Spinner, formatDate,
  inputClass, primaryButtonClass, secondaryButtonClass,
} from '../ui'

interface Reading {
  id: string
  reading_date: string
  reading_value: number
  previous_value: number
  consumption_m3: number
  flag_reason: string | null
  is_estimated: boolean
  recorded_by: string | null
  serial_number: string
  household_id: string
  account_number: string
  head_of_household: string
  community_id: string
  community_name: string
  water_committee_id: string | null
  invoice_number: string | null
}

interface Committee { id: string; name: string }
interface Community { id: string; name: string; water_committee_id: string | null }

export default function ReadingsPage() {
  const [readings, setReadings] = useState<Reading[]>([])
  const [committees, setCommittees] = useState<Committee[]>([])
  const [communities, setCommunities] = useState<Community[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ water_committee_id: '', community_id: '', flagged_only: false, unbilled_only: false, search: '' })
  const [showImport, setShowImport] = useState(false)
  const [importCommunity, setImportCommunity] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ created_households: number; created_meters: number; errors: { row: number; message: string }[] } | null>(null)
  const [importError, setImportError] = useState('')

  useEffect(() => {
    Promise.all([api.get('/water-committees/'), api.get('/communities/')])
      .then(([wc, c]) => { setCommittees(wc.data); setCommunities(c.data) })
      .catch(() => undefined)
  }, [])

  function load() {
    setLoading(true)
    const params: Record<string, string | boolean> = { limit: '500' }
    if (filters.water_committee_id) params.water_committee_id = filters.water_committee_id
    if (filters.community_id) params.community_id = filters.community_id
    if (filters.flagged_only) params.flagged_only = true
    if (filters.unbilled_only) params.unbilled_only = true
    api.get('/readings/', { params }).then((r) => setReadings(r.data)).catch(() => setReadings([])).finally(() => setLoading(false))
  }
  useEffect(load, [filters.water_committee_id, filters.community_id, filters.flagged_only, filters.unbilled_only])

  const visibleCommunities = filters.water_committee_id ? communities.filter((c) => c.water_committee_id === filters.water_committee_id) : communities
  const term = filters.search.trim().toLowerCase()
  const shown = term ? readings.filter((r) => r.account_number.toLowerCase().includes(term) || r.head_of_household.toLowerCase().includes(term) || r.serial_number.toLowerCase().includes(term)) : readings

  async function runImport(e: FormEvent) {
    e.preventDefault()
    if (!file || !importCommunity) return
    setImporting(true); setImportError(''); setImportResult(null)
    const body = new FormData()
    body.append('file', file)
    try {
      const r = await api.post('/readings/import', body, { params: { community_id: importCommunity }, headers: { 'Content-Type': 'multipart/form-data' } })
      setImportResult(r.data)
      if (r.data.errors.length === 0) load()
    } catch (err: any) {
      setImportError(err?.response?.data?.detail ?? 'Import failed.')
    } finally { setImporting(false) }
  }

  return (
    <div>
      <PageHeader
        title="Meter readings"
        subtitle="Every reading as recorded in the field, and the bill each one went into"
        actions={<button onClick={() => { setImportResult(null); setImportError(''); setFile(null); setImportCommunity(communities[0]?.id ?? ''); setShowImport(true) }} className={secondaryButtonClass}><Upload className="h-4 w-4" />Import households (CSV)</button>}
      />
      <Card className="mb-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <Field label="Water committee">
            <select className={inputClass} value={filters.water_committee_id} onChange={(e) => setFilters({ ...filters, water_committee_id: e.target.value, community_id: '' })}>
              <option value="">All</option>{committees.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Community">
            <select className={inputClass} value={filters.community_id} onChange={(e) => setFilters({ ...filters, community_id: e.target.value })}>
              <option value="">All</option>{visibleCommunities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Search"><input className={inputClass} placeholder="Account, name or meter" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm text-gray-700 pb-2"><input type="checkbox" checked={filters.flagged_only} onChange={(e) => setFilters({ ...filters, flagged_only: e.target.checked })} />Flagged only</label>
          <label className="flex items-center gap-2 text-sm text-gray-700 pb-2"><input type="checkbox" checked={filters.unbilled_only} onChange={(e) => setFilters({ ...filters, unbilled_only: e.target.checked })} />Not yet billed</label>
        </div>
      </Card>
      {loading ? <Spinner /> : shown.length === 0 ? (
        <EmptyState icon={Gauge} title="No readings" hint="Readings recorded on the web or synced from Flow Reader appear here." />
      ) : (
        <Card className="p-0 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500"><tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Household</th><th className="px-4 py-3">Community</th><th className="px-4 py-3">Meter</th><th className="px-4 py-3 text-right">Previous</th><th className="px-4 py-3 text-right">Reading</th><th className="px-4 py-3 text-right">Used m³</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Recorded by</th><th className="px-4 py-3">Bill</th></tr></thead>
            <tbody className="divide-y divide-gray-100">
              {shown.map((r) => (
                <tr key={r.id} className={r.flag_reason ? 'bg-amber-50/40' : ''}>
                  <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{formatDate(r.reading_date)}</td>
                  <td className="px-4 py-2"><Link to={`/households/${r.household_id}`} className="text-primary-700 hover:underline">{r.account_number}</Link><span className="text-gray-500"> · {r.head_of_household}</span></td>
                  <td className="px-4 py-2 text-gray-600">{r.community_name}</td>
                  <td className="px-4 py-2 text-gray-600 font-mono text-xs">{r.serial_number}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{r.previous_value}</td>
                  <td className="px-4 py-2 text-right font-medium text-gray-900">{r.reading_value}</td>
                  <td className="px-4 py-2 text-right">{r.consumption_m3}</td>
                  <td className="px-4 py-2">{r.flag_reason ? <Badge value={r.flag_reason} className="bg-amber-100 text-amber-800" /> : r.is_estimated ? <Badge value="estimated" className="bg-gray-100 text-gray-600" /> : <Badge value="ok" className="bg-green-50 text-green-700" />}</td>
                  <td className="px-4 py-2 text-gray-600">{r.recorded_by ?? '—'}</td>
                  <td className="px-4 py-2 text-gray-600">{r.invoice_number ?? <span className="text-gray-400">not billed</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {showImport && (
        <Modal title="Import households from CSV" onClose={() => setShowImport(false)}>
          <form onSubmit={runImport} className="space-y-4">
            <p className="text-sm text-gray-600">Columns: <code>account_number, head_of_household</code> (required), <code>address, phone, members_count, meter_serial_number, meter_brand, meter_initial_reading, notes</code> (optional). Nothing is saved if any row has a problem.</p>
            <Field label="Community">
              <select className={inputClass} value={importCommunity} onChange={(e) => setImportCommunity(e.target.value)} required>
                {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="CSV file"><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required /></Field>
            {importError && <p className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">{importError}</p>}
            {importResult && importResult.errors.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm text-amber-800 max-h-48 overflow-y-auto">
                <p className="font-medium mb-1">Nothing imported. Fix these rows and try again:</p>
                <ul className="list-disc pl-5">{importResult.errors.map((e, i) => <li key={i}>Row {e.row}: {e.message}</li>)}</ul>
              </div>
            )}
            {importResult && importResult.errors.length === 0 && (
              <p className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-3 py-2 text-sm">Imported {importResult.created_households} households and {importResult.created_meters} meters.</p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setShowImport(false)}>Close</button>
              <button type="submit" className={primaryButtonClass} disabled={importing || !file}>{importing ? 'Importing…' : 'Import'}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
